#if PHYSICALAI_OPENXR
using UnityEditor;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features.Interactions;

namespace PhysicalAI.EditorTools
{
    /// <summary>
    /// Meta Quest 2 (PC Quest Link) 구동용 OpenXR 일괄 설정.
    /// - Standalone(Windows) XR 로더 = OpenXR, 시작 시 자동 초기화
    /// - 컨트롤러 프로파일 = Oculus Touch (썸스틱·A/B/X/Y → UnityEngine.XR.InputDevices)
    /// - Active Input Handling = Both (기존 Input.GetKey 코드 유지 + OpenXR 입력)
    /// 배치: Unity -batchmode -quit -executeMethod PhysicalAI.EditorTools.XRSetupAutomation.Setup
    /// </summary>
    public static class XRSetupAutomation
    {
        private const BuildTargetGroup Target = BuildTargetGroup.Standalone;
        private const string XRFolder = "Assets/XR";
        private const string PerTargetAssetPath = XRFolder + "/XRGeneralSettingsPerBuildTarget.asset";
        private const string OpenXRLoaderType = "UnityEngine.XR.OpenXR.OpenXRLoader";
        private const int InputHandlingBoth = 2;

        [MenuItem("PhysicalAI/Setup OpenXR for Quest Link")]
        public static void Setup()
        {
            XRGeneralSettings general = EnsureGeneralSettings();
            general.InitManagerOnStart = true;

            bool assigned = XRPackageMetadataStore.AssignLoader(general.AssignedSettings, OpenXRLoaderType, Target);
            Debug.Log($"[XRSetup] OpenXR loader assigned (Standalone): {assigned || HasOpenXRLoader(general)}");

            OpenXRSettings openxr = OpenXRSettings.GetSettingsForBuildTargetGroup(Target);
            UnityEditor.XR.OpenXR.Features.FeatureHelpers.RefreshFeatures(Target);
            var touch = openxr != null ? openxr.GetFeature<OculusTouchControllerProfile>() : null;
            if (touch != null)
            {
                touch.enabled = true;
                EditorUtility.SetDirty(openxr);
            }
            Debug.Log($"[XRSetup] Oculus Touch Controller Profile enabled: {touch != null && touch.enabled}");

            SetActiveInputHandlingBoth();

            EditorUtility.SetDirty(general);
            AssetDatabase.SaveAssets();
            Debug.Log("[XRSetup] DONE — Quest Link 연결 후 Play");
        }

        private static XRGeneralSettings EnsureGeneralSettings()
        {
            EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget);
            if (perTarget == null)
            {
                if (!AssetDatabase.IsValidFolder(XRFolder)) AssetDatabase.CreateFolder("Assets", "XR");
                perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                AssetDatabase.CreateAsset(perTarget, PerTargetAssetPath);
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
            }
            if (!perTarget.HasSettingsForBuildTarget(Target)) perTarget.CreateDefaultSettingsForBuildTarget(Target);
            if (!perTarget.HasManagerSettingsForBuildTarget(Target)) perTarget.CreateDefaultManagerSettingsForBuildTarget(Target);
            return perTarget.SettingsForBuildTarget(Target);
        }

        private static bool HasOpenXRLoader(XRGeneralSettings general)
        {
            foreach (var loader in general.AssignedSettings.activeLoaders)
            {
                if (loader is OpenXRLoader) return true;
            }
            return false;
        }

        private static void SetActiveInputHandlingBoth()
        {
            var assets = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset");
            if (assets == null || assets.Length == 0) return;
            var so = new SerializedObject(assets[0]);
            var prop = so.FindProperty("activeInputHandler");
            if (prop == null || prop.intValue == InputHandlingBoth) return;
            prop.intValue = InputHandlingBoth;
            so.ApplyModifiedProperties();
            Debug.LogWarning("[XRSetup] Active Input Handling → Both. 에디터 재시작 후 적용됨.");
        }
    }
}
#endif
