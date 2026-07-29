package com.journeyapps.barcodescanner;

import android.content.Context;
import android.view.OrientationEventListener;
import android.view.WindowManager;

/* loaded from: classes11.dex */
public class RotationListener {
    private RotationCallback callback;
    private int lastRotation;
    private OrientationEventListener orientationEventListener;
    private WindowManager windowManager;

    public void listen(Context context, RotationCallback callback) {
        stop();
        Context context2 = context.getApplicationContext();
        this.callback = callback;
        this.windowManager = (WindowManager) context2.getSystemService("window");
        this.orientationEventListener = new OrientationEventListener(context2, 3) { // from class: com.journeyapps.barcodescanner.RotationListener.1
            @Override // android.view.OrientationEventListener
            public void onOrientationChanged(int orientation) {
                int newRotation;
                WindowManager localWindowManager = RotationListener.this.windowManager;
                RotationCallback localCallback = RotationListener.this.callback;
                if (RotationListener.this.windowManager != null && localCallback != null && (newRotation = localWindowManager.getDefaultDisplay().getRotation()) != RotationListener.this.lastRotation) {
                    RotationListener.this.lastRotation = newRotation;
                    localCallback.onRotationChanged(newRotation);
                }
            }
        };
        this.orientationEventListener.enable();
        this.lastRotation = this.windowManager.getDefaultDisplay().getRotation();
    }

    public void stop() {
        if (this.orientationEventListener != null) {
            this.orientationEventListener.disable();
        }
        this.orientationEventListener = null;
        this.windowManager = null;
        this.callback = null;
    }
}
