# Add project specific ProGuard rules here.
-keepattributes Signature
-keepattributes *Annotation*

# Retrofit
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
-dontwarn org.codehaus.mojo.animal_sniffer.IgnoreJRERequirement
-dontwarn javax.annotation.**
-dontwarn kotlin.Unit
-dontwarn retrofit2.KotlinExtensions
-dontwarn retrofit2.KotlinExtensions$*

# Gson
# AI-MOB-APK-002: R8 混淆导致 Gson 反序列化 ApiEnvelope<T>.data 丢失泛型，
# 实际得到 LinkedTreeMap，访问属性抛 ClassCastException（登录即报
# "网络连接失败: ... cannot be cast to ..."）。必须整体 keep（含类名），
# 仅 -keepclassmembers 不够（类名被混淆后 Gson 反射泛型链路断裂）。
-keep class com.factory.wms.data.model.** { *; }
-keep class com.factory.wms.data.api.** { *; }

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Kotlin coroutines
-dontwarn kotlinx.coroutines.**
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory { *; }
-keepnames class kotlinx.coroutines.android.AndroidDispatcherFactory { *; }

# ML Kit barcode / vision
-keep class com.google.mlkit.** { *; }
-dontwarn com.google.mlkit.**

# CameraX
-keep class androidx.camera.** { *; }
-dontwarn androidx.camera.**

# EncryptedSharedPreferences / security crypto
-keep class androidx.security.crypto.** { *; }
-dontwarn androidx.security.crypto.**

# Room
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-dontwarn androidx.room.**
# AI-MOB-APK-003: Compose UI 包整体 keep（类名不混淆）。
# R8 混淆 ui 包可能导致 Compose 组合/重组异常（如部分组件不渲染），
# 保留类名与成员确保 UI 稳定。
-keep class com.factory.wms.ui.** { *; }
-keepattributes SourceFile,LineNumberTable