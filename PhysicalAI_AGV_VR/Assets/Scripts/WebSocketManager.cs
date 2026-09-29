using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace PhysicalAI.VR
{
    /// <summary>
    /// Meta Quest 2 및 Unity Editor 환경에서 동작하는 C# 표준 비동기 WebSocket 매니저
    /// 외부 라이브러리 없이 .NET 표준 ClientWebSocket 활용
    /// </summary>
    public class WebSocketManager : MonoBehaviour
    {
        [Header("연결 설정")]
        [Tooltip("Physical AI Relay Agent 주소 (예: ws://192.168.0.15:9090)")]
        public string serverUri = "ws://127.0.0.1:9090";
        public bool connectOnStart = true;

        private ClientWebSocket _webSocket;
        private CancellationTokenSource _cts;

        // 메인 스레드로 바이너리(영상) 및 텍스트 데이터 전달용 큐
        private readonly ConcurrentQueue<byte[]> _imageQueue = new ConcurrentQueue<byte[]>();
        private readonly ConcurrentQueue<string> _messageQueue = new ConcurrentQueue<string>();

        public event Action<byte[]> OnImageFrameReceived;
        public event Action<string> OnTextReceived;
        public bool IsConnected => _webSocket != null && _webSocket.State == WebSocketState.Open;

        private async void Start()
        {
            if (connectOnStart)
            {
                await ConnectAsync();
            }
        }

        public async Task ConnectAsync()
        {
            if (IsConnected) return;

            try
            {
                _cts = new CancellationTokenSource();
                _webSocket = new ClientWebSocket();
                Debug.Log($"[WebSocket] Connecting to {serverUri}...");
                await _webSocket.ConnectAsync(new Uri(serverUri), _cts.Token);
                Debug.Log("[WebSocket] Connected successfully!");

                _ = Task.Run(ReceiveLoop, _cts.Token);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[WebSocket] Connection failed: {ex.Message}");
            }
        }

        private async Task ReceiveLoop()
        {
            byte[] buffer = new byte[1024 * 512]; // 512KB 버퍼 (VGA JPEG 수신용)
            var segment = new ArraySegment<byte>(buffer);

            while (_webSocket.State == WebSocketState.Open && !_cts.IsCancellationRequested)
            {
                try
                {
                    WebSocketReceiveResult result = await _webSocket.ReceiveAsync(segment, _cts.Token);

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await _webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", CancellationToken.None);
                        break;
                    }
                    else if (result.MessageType == WebSocketMessageType.Binary)
                    {
                        // JPEG 이미지 프레임 수신
                        byte[] frameData = new byte[result.Count];
                        Array.Copy(buffer, frameData, result.Count);
                        _imageQueue.Enqueue(frameData);
                    }
                    else if (result.MessageType == WebSocketMessageType.Text)
                    {
                        string msg = Encoding.UTF8.GetString(buffer, 0, result.Count);
                        _messageQueue.Enqueue(msg);
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[WebSocket] Receive error: {ex.Message}");
                    break;
                }
            }
        }

        public async Task SendTextAsync(string message)
        {
            if (!IsConnected) return;

            byte[] data = Encoding.UTF8.GetBytes(message);
            await _webSocket.SendAsync(new ArraySegment<byte>(data), WebSocketMessageType.Text, true, CancellationToken.None);
        }

        private void Update()
        {
            // 백그라운드 스레드에서 수신한 데이터를 Unity 메인 스레드 이벤트로 발행
            while (_imageQueue.TryDequeue(out byte[] frame))
            {
                OnImageFrameReceived?.Invoke(frame);
            }

            while (_messageQueue.TryDequeue(out string text))
            {
                OnTextReceived?.Invoke(text);
            }
        }

        private async void OnDestroy()
        {
            if (_webSocket != null)
            {
                _cts?.Cancel();
                if (_webSocket.State == WebSocketState.Open)
                {
                    await _webSocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "App Quit", CancellationToken.None);
                }
                _webSocket.Dispose();
            }
        }
    }
}
