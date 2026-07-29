package com.journeyapps.barcodescanner.camera;

import android.hardware.Camera;
import android.os.Handler;
import android.os.Message;
import android.util.Log;
import com.journeyapps.barcodescanner.camera.AutoFocusManager;
import java.util.ArrayList;
import java.util.Collection;
import kotlinx.coroutines.DebugKt;

/* loaded from: classes11.dex */
public final class AutoFocusManager {
    private static final long AUTO_FOCUS_INTERVAL_MS = 2000;
    private final Camera camera;
    private boolean focusing;
    private boolean stopped;
    private final boolean useAutoFocus;
    private static final String TAG = AutoFocusManager.class.getSimpleName();
    private static final Collection<String> FOCUS_MODES_CALLING_AF = new ArrayList(2);
    private int MESSAGE_FOCUS = 1;
    private final Handler.Callback focusHandlerCallback = new Handler.Callback() { // from class: com.journeyapps.barcodescanner.camera.AutoFocusManager.1
        @Override // android.os.Handler.Callback
        public boolean handleMessage(Message msg) {
            if (msg.what == AutoFocusManager.this.MESSAGE_FOCUS) {
                AutoFocusManager.this.focus();
                return true;
            }
            return false;
        }
    };
    private final Camera.AutoFocusCallback autoFocusCallback = new AnonymousClass2();
    private Handler handler = new Handler(this.focusHandlerCallback);

    static {
        FOCUS_MODES_CALLING_AF.add(DebugKt.DEBUG_PROPERTY_VALUE_AUTO);
        FOCUS_MODES_CALLING_AF.add("macro");
    }

    /* renamed from: com.journeyapps.barcodescanner.camera.AutoFocusManager$2, reason: invalid class name */
    class AnonymousClass2 implements Camera.AutoFocusCallback {
        AnonymousClass2() {
        }

        @Override // android.hardware.Camera.AutoFocusCallback
        public void onAutoFocus(boolean success, Camera theCamera) {
            AutoFocusManager.this.handler.post(new Runnable() { // from class: com.journeyapps.barcodescanner.camera.AutoFocusManager$2$$ExternalSyntheticLambda0
                @Override // java.lang.Runnable
                public final void run() {
                    AutoFocusManager.AnonymousClass2.this.m6469x7b23e9dd();
                }
            });
        }

        /* renamed from: lambda$onAutoFocus$0$com-journeyapps-barcodescanner-camera-AutoFocusManager$2, reason: not valid java name */
        /* synthetic */ void m6469x7b23e9dd() {
            AutoFocusManager.this.focusing = false;
            AutoFocusManager.this.autoFocusAgainLater();
        }
    }

    public AutoFocusManager(Camera camera, CameraSettings settings) {
        this.camera = camera;
        String currentFocusMode = camera.getParameters().getFocusMode();
        this.useAutoFocus = settings.isAutoFocusEnabled() && FOCUS_MODES_CALLING_AF.contains(currentFocusMode);
        Log.i(TAG, "Current focus mode '" + currentFocusMode + "'; use auto focus? " + this.useAutoFocus);
        start();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public synchronized void autoFocusAgainLater() {
        if (!this.stopped && !this.handler.hasMessages(this.MESSAGE_FOCUS)) {
            this.handler.sendMessageDelayed(this.handler.obtainMessage(this.MESSAGE_FOCUS), AUTO_FOCUS_INTERVAL_MS);
        }
    }

    public void start() {
        this.stopped = false;
        focus();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void focus() {
        if (this.useAutoFocus && !this.stopped && !this.focusing) {
            try {
                this.camera.autoFocus(this.autoFocusCallback);
                this.focusing = true;
            } catch (RuntimeException re) {
                Log.w(TAG, "Unexpected exception while focusing", re);
                autoFocusAgainLater();
            }
        }
    }

    private void cancelOutstandingTask() {
        this.handler.removeMessages(this.MESSAGE_FOCUS);
    }

    public void stop() {
        this.stopped = true;
        this.focusing = false;
        cancelOutstandingTask();
        if (this.useAutoFocus) {
            try {
                this.camera.cancelAutoFocus();
            } catch (RuntimeException re) {
                Log.w(TAG, "Unexpected exception while cancelling focusing", re);
            }
        }
    }
}
