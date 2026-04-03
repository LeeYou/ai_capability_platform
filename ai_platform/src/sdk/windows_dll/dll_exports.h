#ifndef AI_PLATFORM_DLL_EXPORTS_H
#define AI_PLATFORM_DLL_EXPORTS_H

#ifdef _WIN32
#define AI_SDK_EXPORT __declspec(dllexport)
#else
#define AI_SDK_EXPORT
#endif

extern "C" AI_SDK_EXPORT int ai_sdk_get_version();

#endif
