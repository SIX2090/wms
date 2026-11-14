package com.factory.wms

import android.app.Application
import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageInfo
import android.content.pm.Signature
import android.content.pm.SigningInfo
import androidx.test.core.app.ApplicationProvider
import com.android.apksig.ApkVerifier
import com.factory.wms.update.*
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.shadow.api.Shadow
import java.io.File
import java.security.MessageDigest
import java.util.Base64

/** A tiny no-code APK signed with a disposable synthetic certificate, no private key committed. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], application = Application::class)
class ApkUpdateVerifierTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()
    private lateinit var apk: File
    private lateinit var cert: ByteArray
    private fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    @Before fun setup() {
        apk = File(context.cacheDir, "synthetic-signed-update.apk")
        apk.writeBytes(Base64.getDecoder().decode(javaClass.classLoader!!
            .getResourceAsStream("update-test.apk.b64")!!.bufferedReader().readText()))
        val checked = ApkVerifier.Builder(apk).setMinCheckedPlatformVersion(31).build().verify()
        assertTrue(checked.isVerified)
        cert = checked.signerCertificates.single().encoded
        installed(cert)
        Shadows.shadowOf(context.packageManager).setPackageArchiveInfo(apk.absolutePath,
            PackageInfo().apply {
                packageName = "com.factory.wms.mobile"; setLongVersionCode(41); versionName = "test-41"
                applicationInfo = ApplicationInfo().apply { minSdkVersion = 26 }
            })
    }

    private fun installed(signer: ByteArray) {
        val info = Shadow.newInstanceOf(SigningInfo::class.java)
        Shadows.shadowOf(info).setSignatures(arrayOf(Signature(signer)))
        Shadows.shadowOf(context.packageManager).installPackage(PackageInfo().apply {
            packageName = "com.factory.wms.mobile"; setLongVersionCode(40); signingInfo = info
            applicationInfo = ApplicationInfo(context.applicationInfo)
        })
    }

    private fun metadata() = UpdateRelease("com.factory.wms.mobile", 41, "test-41", 26,
        "https://github.com/SIX2090/wms/releases/download/android-apk-900/wms-mobile-scan.apk",
        apk.length(), apk.sha256(), digest(cert), "a".repeat(40), "synthetic")

    @Test fun cryptographicallyValidApkWithCompatibleInstalledCertificatePasses() {
        ApkUpdateVerifier(context).verify(apk, metadata())
    }

    @Test fun validApkFromAnotherSignerCannotReplaceInstalledApp() {
        installed("another synthetic signer".toByteArray())
        assertThrows(IllegalArgumentException::class.java) {
            ApkUpdateVerifier(context).verify(apk, metadata())
        }
    }

    @Test fun changedSignedContentFailsEvenWithNewMatchingFileHash() {
        val changed = apk.readBytes()
        changed[100] = (changed[100].toInt() xor 1).toByte()
        apk.writeBytes(changed)
        assertThrows(Exception::class.java) { ApkUpdateVerifier(context).verify(apk, metadata()) }
    }

    @Test fun validPackageCannotHideDifferentVersionOrDeclaredCertificate() {
        val meta = metadata()
        for (bad in listOf(meta.copy(versionCode = 42), meta.copy(certificateSha256 = "e".repeat(64)),
                meta.copy(versionName = "wrong"), meta.copy(minSdk = 27))) {
            assertThrows(IllegalArgumentException::class.java) { ApkUpdateVerifier(context).verify(apk, bad) }
        }
    }
}
