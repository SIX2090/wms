package com.factory.wms.update

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import com.android.apksig.ApkVerifier
import java.io.File
import java.security.MessageDigest

internal class ApkUpdateVerifier(private val context: Context) {
    @Suppress("DEPRECATION")
    fun verify(file: File, release: UpdateRelease) {
        val manager = context.packageManager
        val installed = manager.getPackageInfo(context.packageName,
            if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES
            else PackageManager.GET_SIGNATURES)
        val currentCode = if (Build.VERSION.SDK_INT >= 28) installed.longVersionCode
            else installed.versionCode.toLong()
        release.validate(context.packageName, currentCode, Build.VERSION.SDK_INT)
        require(file.length() == release.size && file.sha256() == release.sha256) { "更新文件已变化" }
        // PackageManager parsing alone does not verify the APK's cryptographic signature.
        val checked = ApkVerifier.Builder(file).setMinCheckedPlatformVersion(Build.VERSION.SDK_INT)
            .setMaxCheckedPlatformVersion(Build.VERSION.SDK_INT).build().verify()
        require(checked.isVerified && checked.signerCertificates.size == 1) { "更新包签名验证失败" }
        val digest = MessageDigest.getInstance("SHA-256")
        fun fingerprint(bytes: ByteArray) = digest.digest(bytes).joinToString("") { "%02x".format(it) }
        val signer = fingerprint(checked.signerCertificates.single().encoded)
        val existing = if (Build.VERSION.SDK_INT >= 28) installed.signingInfo?.apkContentsSigners
            else installed.signatures
        require(existing?.size == 1 && signer == fingerprint(existing.single().toByteArray()) &&
            signer == release.certificateSha256) { "更新签名与当前应用不一致，请联系维护人员" }
        val archive = requireNotNull(manager.getPackageArchiveInfo(file.absolutePath, 0)) { "更新包无法解析" }
        val archiveCode = if (Build.VERSION.SDK_INT >= 28) archive.longVersionCode
            else archive.versionCode.toLong()
        require(archive.packageName == release.packageName && archiveCode == release.versionCode &&
            archive.versionName == release.versionName &&
            archive.applicationInfo?.minSdkVersion == release.minSdk) { "更新包与发行清单不一致" }
    }
}
