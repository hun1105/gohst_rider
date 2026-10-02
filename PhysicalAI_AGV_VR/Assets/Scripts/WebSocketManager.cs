using System;
using System.Collections.Concurrent;
using System.IO;
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
    /// - 자동 재접속 (릴레이가 Unity보다 늦게 켜지거나 끊겨도 복구)
    /// - 분할 수신 프레임을 EndOfMessage까지 조립 (Wi-Fi 경유 JPEG 깨짐 방지)
    /// - 송신 직렬화 (ClientWebSocket은 동시 SendAsync 불가 → STOP 등 명령 유실 방지)
    /// </summary>
    public class WebSocketManager : MonoBehaviour
    {
        [Header("연결 설정")]
        [Tooltip("Physical AI Relay Agent 주소 (예: ws://192.168.0.15:9090)")]
        public string serverUri = "ws://127.0.0.1:9090";
        public bool connectOnStart = true;
        [Tooltip("연결 실패·끊김 후 재접속 간격 (초)")]
        public float reconnectInterval = 2.0f;
        [Tooltip("송신 대기 한도 (ms). 초과 시 해당 명령 폐기 (다음 20Hz 명령이 대체)")]
        public int sendLockTimeoutMs = 200;

        private const int ReceiveChunkBytes = 64 * 1024;
        private const int MaxMessageBytes = 4 * 1024 * 1024;

        private ClientWebSocket _webSocket;
        private CancellationTokenSource _lifetimeCts;
        private readonly SemaphoreSlim _sendLock = new SemaphoreSlim(1, 1);

        // 영상은 최신 프레임만 유지 (메인 스레드 지연 시 누적 방지), 텍스트는 순서 보존
        private byte[] _latestFrame;
        private readonly ConcurrentQueue<string> _messageQueue = new ConcurrentQueue<string>();

        public event Action<byte[]> OnImageFrameReceived;
        public event Action<string> OnTextReceived;
        public bool IsConnected => _webSocket != null && _webSocket.State == WebSocketState.Open;

        private void Start()
        {
            _lifetimeCts = new CancellationTokenSource();
            if (connectOnStart)
            {
                _ = ConnectionLoop(_lifetimeCts.Token);
            }
        }

        /// <summary>연결 유지 루프: 끊기면 reconnectInterval 후 재접속.</summary>
        private async Task ConnectionLoop(CancellationToken token)
        {
            bool loggedFailure = false;
            while (!token.IsCancellationRequested)
            {
                var ws = new ClientWebSocket();
                try
                {
                    await ws.ConnectAsync(new Uri(serverUri), token);
                    _webSocket = ws;
                    loggedFailure = false;
                    Debug.Log($"[WebSocket] Connected: {serverUri}");
                    await Task.Run(() => ReceiveLoop(ws, token), token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    if (!loggedFailure)
                    {
                        Debug.LogWarning($"[WebSocket] {serverUri} 연결 실패/끊김: {ex.Message} → {reconnectInterval}s마다 재시도");
                        loggedFailure = true;
                    }
                }
                finally
                {
                    if (_webSocket == ws) _webSocket = null;
                    ws.Dispose();
                }

                try { await Task.Delay(TimeSpan.FromSeconds(reconnectInterval), token); }
                catch (OperationCanceledException) { break; }
            }
        }

        private async Task ReceiveLoop(ClientWebSocket ws, CancellationToken token)
        {
            byte[] chunk = new byte[ReceiveChunkBytes];
            var segment = new ArraySegment<byte>(chunk);
            using var message = new MemoryStream();

            while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                WebSocketReceiveResult result = await ws.ReceiveAsync(segment, token);
                if (result.MessageType == WebSocketMessageType.Close)
                {
                    await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", CancellationToken.None);
                    Debug.LogWarning("[WebSocket] Server closed connection");
                    return;
                }

                message.Write(chunk, 0, result.Count);
                if (message.Length > MaxMessageBytes)
                {
                    throw new InvalidDataException($"message > {MaxMessageBytes} bytes");
                }
                if (!result.EndOfMessage) continue;

                if (result.MessageType == WebSocketMessageType.Binary)
                {
                    Volatile.Write(ref _latestFrame, message.ToArray());  // JPEG 프레임
                }
                else
                {
                    _messageQueue.Enqueue(Encoding.UTF8.GetString(message.GetBuffer(), 0, (int)message.Length));
                }
                message.SetLength(0);
            }
        }

        public async Task SendTextAsync(string message)
        {
            var ws = _webSocket;
            if (ws == null || ws.State != WebSocketState.Open) return;

            if (!await _sendLock.WaitAsync(sendLockTimeoutMs)) return;
            try
            {
                byte[] data = Encoding.UTF8.GetBytes(message);
                await ws.SendAsync(new ArraySegment<byte>(data), WebSocketMessageType.Text, true, CancellationToken.None);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[WebSocket] Send failed: {ex.Message}");
            }
            finally
            {
                _sendLock.Release();
            }
        }

        private void Update()
        {
            // 백그라운드 스레드에서 수신한 데이터를 Unity 메인 스레드 이벤트로 발행
            byte[] frame = Interlocked.Exchange(ref _latestFrame, null);
            if (frame != null)
            {
                OnImageFrameReceived?.Invoke(frame);
            }

            while (_messageQueue.TryDequeue(out string text))
            {
                OnTextReceived?.Invoke(text);
            }
        }

        private void OnDestroy()
        {
            _lifetimeCts?.Cancel();
            var ws = _webSocket;
            if (ws != null && ws.State == WebSocketState.Open)
            {
                // 종료 대기하지 않음 (에디터 Play 종료 지연 방지). 릴레이는 연결 해제 시 로봇 정지.
                _ = ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "App Quit", CancellationToken.None);
            }
        }
    }
}
