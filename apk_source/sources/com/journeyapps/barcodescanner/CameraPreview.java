package com.journeyapps.barcodescanner;

import android.content.Context;
import android.content.res.TypedArray;
import android.graphics.Matrix;
import android.graphics.Rect;
import android.graphics.SurfaceTexture;
import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.os.Parcelable;
import android.util.AttributeSet;
import android.util.Log;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.TextureView;
import android.view.ViewGroup;
import android.view.WindowManager;
import androidx.core.view.ViewCompat;
import com.google.zxing.client.android.R;
import com.journeyapps.barcodescanner.CameraPreview;
import com.journeyapps.barcodescanner.camera.CameraInstance;
import com.journeyapps.barcodescanner.camera.CameraParametersCallback;
import com.journeyapps.barcodescanner.camera.CameraSettings;
import com.journeyapps.barcodescanner.camera.CameraSurface;
import com.journeyapps.barcodescanner.camera.CenterCropStrategy;
import com.journeyapps.barcodescanner.camera.DisplayConfiguration;
import com.journeyapps.barcodescanner.camera.FitCenterStrategy;
import com.journeyapps.barcodescanner.camera.FitXYStrategy;
import com.journeyapps.barcodescanner.camera.PreviewScalingStrategy;
import java.util.ArrayList;
import java.util.List;

/* loaded from: classes11.dex */
public class CameraPreview extends ViewGroup {
    private static final int ROTATION_LISTENER_DELAY_MS = 250;
    private static final String TAG = CameraPreview.class.getSimpleName();
    private CameraInstance cameraInstance;
    private CameraSettings cameraSettings;
    private Size containerSize;
    private Size currentSurfaceSize;
    private DisplayConfiguration displayConfiguration;
    private final StateListener fireState;
    private Rect framingRect;
    private Size framingRectSize;
    private double marginFraction;
    private int openedOrientation;
    private boolean previewActive;
    private Rect previewFramingRect;
    private PreviewScalingStrategy previewScalingStrategy;
    private Size previewSize;
    private RotationCallback rotationCallback;
    private RotationListener rotationListener;
    private final Handler.Callback stateCallback;
    private Handler stateHandler;
    private List<StateListener> stateListeners;
    private final SurfaceHolder.Callback surfaceCallback;
    private Rect surfaceRect;
    private SurfaceView surfaceView;
    private TextureView textureView;
    private boolean torchOn;
    private boolean useTextureView;
    private WindowManager windowManager;

    public interface StateListener {
        void cameraClosed();

        void cameraError(Exception exc);

        void previewSized();

        void previewStarted();

        void previewStopped();
    }

    private TextureView.SurfaceTextureListener surfaceTextureListener() {
        return new TextureView.SurfaceTextureListener() { // from class: com.journeyapps.barcodescanner.CameraPreview.1
            @Override // android.view.TextureView.SurfaceTextureListener
            public void onSurfaceTextureAvailable(SurfaceTexture surface, int width, int height) {
                onSurfaceTextureSizeChanged(surface, width, height);
            }

            @Override // android.view.TextureView.SurfaceTextureListener
            public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int width, int height) {
                CameraPreview.this.currentSurfaceSize = new Size(width, height);
                CameraPreview.this.startPreviewIfReady();
            }

            @Override // android.view.TextureView.SurfaceTextureListener
            public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) {
                return false;
            }

            @Override // android.view.TextureView.SurfaceTextureListener
            public void onSurfaceTextureUpdated(SurfaceTexture surface) {
            }
        };
    }

    /* renamed from: com.journeyapps.barcodescanner.CameraPreview$4, reason: invalid class name */
    class AnonymousClass4 implements RotationCallback {
        AnonymousClass4() {
        }

        /* renamed from: lambda$onRotationChanged$0$com-journeyapps-barcodescanner-CameraPreview$4, reason: not valid java name */
        /* synthetic */ void m6464xa84c9589() {
            CameraPreview.this.rotationChanged();
        }

        @Override // com.journeyapps.barcodescanner.RotationCallback
        public void onRotationChanged(int rotation) {
            CameraPreview.this.stateHandler.postDelayed(new Runnable() { // from class: com.journeyapps.barcodescanner.CameraPreview$4$$ExternalSyntheticLambda0
                @Override // java.lang.Runnable
                public final void run() {
                    CameraPreview.AnonymousClass4.this.m6464xa84c9589();
                }
            }, 250L);
        }
    }

    public CameraPreview(Context context) {
        super(context);
        this.useTextureView = false;
        this.previewActive = false;
        this.openedOrientation = -1;
        this.stateListeners = new ArrayList();
        this.cameraSettings = new CameraSettings();
        this.framingRect = null;
        this.previewFramingRect = null;
        this.framingRectSize = null;
        this.marginFraction = 0.1d;
        this.previewScalingStrategy = null;
        this.torchOn = false;
        this.surfaceCallback = new SurfaceHolder.Callback() { // from class: com.journeyapps.barcodescanner.CameraPreview.2
            @Override // android.view.SurfaceHolder.Callback
            public void surfaceCreated(SurfaceHolder holder) {
            }

            @Override // android.view.SurfaceHolder.Callback
            public void surfaceDestroyed(SurfaceHolder holder) {
                CameraPreview.this.currentSurfaceSize = null;
            }

            @Override // android.view.SurfaceHolder.Callback
            public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
                if (holder == null) {
                    Log.e(CameraPreview.TAG, "*** WARNING *** surfaceChanged() gave us a null surface!");
                    return;
                }
                CameraPreview.this.currentSurfaceSize = new Size(width, height);
                CameraPreview.this.startPreviewIfReady();
            }
        };
        this.stateCallback = new Handler.Callback() { // from class: com.journeyapps.barcodescanner.CameraPreview.3
            @Override // android.os.Handler.Callback
            public boolean handleMessage(Message message) {
                if (message.what == R.id.zxing_prewiew_size_ready) {
                    CameraPreview.this.previewSized((Size) message.obj);
                    return true;
                }
                if (message.what == R.id.zxing_camera_error) {
                    Exception error = (Exception) message.obj;
                    if (CameraPreview.this.isActive()) {
                        CameraPreview.this.pause();
                        CameraPreview.this.fireState.cameraError(error);
                        return false;
                    }
                    return false;
                }
                if (message.what == R.id.zxing_camera_closed) {
                    CameraPreview.this.fireState.cameraClosed();
                    return false;
                }
                return false;
            }
        };
        this.rotationCallback = new AnonymousClass4();
        this.fireState = new StateListener() { // from class: com.journeyapps.barcodescanner.CameraPreview.5
            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewSized() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewSized();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewStarted() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewStarted();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewStopped() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewStopped();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void cameraError(Exception error) {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.cameraError(error);
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void cameraClosed() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.cameraClosed();
                }
            }
        };
        initialize(context, null, 0, 0);
    }

    public CameraPreview(Context context, AttributeSet attrs) {
        super(context, attrs);
        this.useTextureView = false;
        this.previewActive = false;
        this.openedOrientation = -1;
        this.stateListeners = new ArrayList();
        this.cameraSettings = new CameraSettings();
        this.framingRect = null;
        this.previewFramingRect = null;
        this.framingRectSize = null;
        this.marginFraction = 0.1d;
        this.previewScalingStrategy = null;
        this.torchOn = false;
        this.surfaceCallback = new SurfaceHolder.Callback() { // from class: com.journeyapps.barcodescanner.CameraPreview.2
            @Override // android.view.SurfaceHolder.Callback
            public void surfaceCreated(SurfaceHolder holder) {
            }

            @Override // android.view.SurfaceHolder.Callback
            public void surfaceDestroyed(SurfaceHolder holder) {
                CameraPreview.this.currentSurfaceSize = null;
            }

            @Override // android.view.SurfaceHolder.Callback
            public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
                if (holder == null) {
                    Log.e(CameraPreview.TAG, "*** WARNING *** surfaceChanged() gave us a null surface!");
                    return;
                }
                CameraPreview.this.currentSurfaceSize = new Size(width, height);
                CameraPreview.this.startPreviewIfReady();
            }
        };
        this.stateCallback = new Handler.Callback() { // from class: com.journeyapps.barcodescanner.CameraPreview.3
            @Override // android.os.Handler.Callback
            public boolean handleMessage(Message message) {
                if (message.what == R.id.zxing_prewiew_size_ready) {
                    CameraPreview.this.previewSized((Size) message.obj);
                    return true;
                }
                if (message.what == R.id.zxing_camera_error) {
                    Exception error = (Exception) message.obj;
                    if (CameraPreview.this.isActive()) {
                        CameraPreview.this.pause();
                        CameraPreview.this.fireState.cameraError(error);
                        return false;
                    }
                    return false;
                }
                if (message.what == R.id.zxing_camera_closed) {
                    CameraPreview.this.fireState.cameraClosed();
                    return false;
                }
                return false;
            }
        };
        this.rotationCallback = new AnonymousClass4();
        this.fireState = new StateListener() { // from class: com.journeyapps.barcodescanner.CameraPreview.5
            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewSized() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewSized();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewStarted() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewStarted();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewStopped() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewStopped();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void cameraError(Exception error) {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.cameraError(error);
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void cameraClosed() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.cameraClosed();
                }
            }
        };
        initialize(context, attrs, 0, 0);
    }

    public CameraPreview(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        this.useTextureView = false;
        this.previewActive = false;
        this.openedOrientation = -1;
        this.stateListeners = new ArrayList();
        this.cameraSettings = new CameraSettings();
        this.framingRect = null;
        this.previewFramingRect = null;
        this.framingRectSize = null;
        this.marginFraction = 0.1d;
        this.previewScalingStrategy = null;
        this.torchOn = false;
        this.surfaceCallback = new SurfaceHolder.Callback() { // from class: com.journeyapps.barcodescanner.CameraPreview.2
            @Override // android.view.SurfaceHolder.Callback
            public void surfaceCreated(SurfaceHolder holder) {
            }

            @Override // android.view.SurfaceHolder.Callback
            public void surfaceDestroyed(SurfaceHolder holder) {
                CameraPreview.this.currentSurfaceSize = null;
            }

            @Override // android.view.SurfaceHolder.Callback
            public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
                if (holder == null) {
                    Log.e(CameraPreview.TAG, "*** WARNING *** surfaceChanged() gave us a null surface!");
                    return;
                }
                CameraPreview.this.currentSurfaceSize = new Size(width, height);
                CameraPreview.this.startPreviewIfReady();
            }
        };
        this.stateCallback = new Handler.Callback() { // from class: com.journeyapps.barcodescanner.CameraPreview.3
            @Override // android.os.Handler.Callback
            public boolean handleMessage(Message message) {
                if (message.what == R.id.zxing_prewiew_size_ready) {
                    CameraPreview.this.previewSized((Size) message.obj);
                    return true;
                }
                if (message.what == R.id.zxing_camera_error) {
                    Exception error = (Exception) message.obj;
                    if (CameraPreview.this.isActive()) {
                        CameraPreview.this.pause();
                        CameraPreview.this.fireState.cameraError(error);
                        return false;
                    }
                    return false;
                }
                if (message.what == R.id.zxing_camera_closed) {
                    CameraPreview.this.fireState.cameraClosed();
                    return false;
                }
                return false;
            }
        };
        this.rotationCallback = new AnonymousClass4();
        this.fireState = new StateListener() { // from class: com.journeyapps.barcodescanner.CameraPreview.5
            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewSized() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewSized();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewStarted() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewStarted();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void previewStopped() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.previewStopped();
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void cameraError(Exception error) {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.cameraError(error);
                }
            }

            @Override // com.journeyapps.barcodescanner.CameraPreview.StateListener
            public void cameraClosed() {
                for (StateListener listener : CameraPreview.this.stateListeners) {
                    listener.cameraClosed();
                }
            }
        };
        initialize(context, attrs, defStyleAttr, 0);
    }

    private void initialize(Context context, AttributeSet attrs, int defStyleAttr, int defStyleRes) {
        if (getBackground() == null) {
            setBackgroundColor(ViewCompat.MEASURED_STATE_MASK);
        }
        initializeAttributes(attrs);
        this.windowManager = (WindowManager) context.getSystemService("window");
        this.stateHandler = new Handler(this.stateCallback);
        this.rotationListener = new RotationListener();
    }

    @Override // android.view.ViewGroup, android.view.View
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        setupSurfaceView();
    }

    protected void initializeAttributes(AttributeSet attrs) {
        TypedArray styledAttributes = getContext().obtainStyledAttributes(attrs, R.styleable.zxing_camera_preview);
        int framingRectWidth = (int) styledAttributes.getDimension(R.styleable.zxing_camera_preview_zxing_framing_rect_width, -1.0f);
        int framingRectHeight = (int) styledAttributes.getDimension(R.styleable.zxing_camera_preview_zxing_framing_rect_height, -1.0f);
        if (framingRectWidth > 0 && framingRectHeight > 0) {
            this.framingRectSize = new Size(framingRectWidth, framingRectHeight);
        }
        this.useTextureView = styledAttributes.getBoolean(R.styleable.zxing_camera_preview_zxing_use_texture_view, true);
        int scalingStrategyNumber = styledAttributes.getInteger(R.styleable.zxing_camera_preview_zxing_preview_scaling_strategy, -1);
        if (scalingStrategyNumber == 1) {
            this.previewScalingStrategy = new CenterCropStrategy();
        } else if (scalingStrategyNumber == 2) {
            this.previewScalingStrategy = new FitCenterStrategy();
        } else if (scalingStrategyNumber == 3) {
            this.previewScalingStrategy = new FitXYStrategy();
        }
        styledAttributes.recycle();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void rotationChanged() {
        if (isActive() && getDisplayRotation() != this.openedOrientation) {
            pause();
            resume();
        }
    }

    private void setupSurfaceView() {
        if (this.useTextureView) {
            this.textureView = new TextureView(getContext());
            this.textureView.setSurfaceTextureListener(surfaceTextureListener());
            addView(this.textureView);
        } else {
            this.surfaceView = new SurfaceView(getContext());
            this.surfaceView.getHolder().addCallback(this.surfaceCallback);
            addView(this.surfaceView);
        }
    }

    public void addStateListener(StateListener listener) {
        this.stateListeners.add(listener);
    }

    private void calculateFrames() {
        if (this.containerSize == null || this.previewSize == null || this.displayConfiguration == null) {
            this.previewFramingRect = null;
            this.framingRect = null;
            this.surfaceRect = null;
            throw new IllegalStateException("containerSize or previewSize is not set yet");
        }
        int previewWidth = this.previewSize.width;
        int previewHeight = this.previewSize.height;
        int width = this.containerSize.width;
        int height = this.containerSize.height;
        Rect scaledPreview = this.displayConfiguration.scalePreview(this.previewSize);
        if (scaledPreview.width() <= 0 || scaledPreview.height() <= 0) {
            return;
        }
        this.surfaceRect = scaledPreview;
        Rect container = new Rect(0, 0, width, height);
        this.framingRect = calculateFramingRect(container, this.surfaceRect);
        Rect frameInPreview = new Rect(this.framingRect);
        frameInPreview.offset(-this.surfaceRect.left, -this.surfaceRect.top);
        this.previewFramingRect = new Rect((frameInPreview.left * previewWidth) / this.surfaceRect.width(), (frameInPreview.top * previewHeight) / this.surfaceRect.height(), (frameInPreview.right * previewWidth) / this.surfaceRect.width(), (frameInPreview.bottom * previewHeight) / this.surfaceRect.height());
        if (this.previewFramingRect == null || this.previewFramingRect.width() <= 0 || this.previewFramingRect.height() <= 0) {
            this.previewFramingRect = null;
            this.framingRect = null;
            Log.w(TAG, "Preview frame is too small");
            return;
        }
        this.fireState.previewSized();
    }

    public void setTorch(boolean on) {
        this.torchOn = on;
        if (this.cameraInstance != null) {
            this.cameraInstance.setTorch(on);
        }
    }

    public void changeCameraParameters(CameraParametersCallback callback) {
        if (this.cameraInstance != null) {
            this.cameraInstance.changeCameraParameters(callback);
        }
    }

    private void containerSized(Size containerSize) {
        this.containerSize = containerSize;
        if (this.cameraInstance != null && this.cameraInstance.getDisplayConfiguration() == null) {
            this.displayConfiguration = new DisplayConfiguration(getDisplayRotation(), containerSize);
            this.displayConfiguration.setPreviewScalingStrategy(getPreviewScalingStrategy());
            this.cameraInstance.setDisplayConfiguration(this.displayConfiguration);
            this.cameraInstance.configureCamera();
            if (this.torchOn) {
                this.cameraInstance.setTorch(this.torchOn);
            }
        }
    }

    public void setPreviewScalingStrategy(PreviewScalingStrategy previewScalingStrategy) {
        this.previewScalingStrategy = previewScalingStrategy;
    }

    public PreviewScalingStrategy getPreviewScalingStrategy() {
        if (this.previewScalingStrategy != null) {
            return this.previewScalingStrategy;
        }
        if (this.textureView != null) {
            return new CenterCropStrategy();
        }
        return new FitCenterStrategy();
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void previewSized(Size size) {
        this.previewSize = size;
        if (this.containerSize != null) {
            calculateFrames();
            requestLayout();
            startPreviewIfReady();
        }
    }

    protected Matrix calculateTextureTransform(Size textureSize, Size previewSize) {
        float scaleX;
        float scaleY;
        float ratioTexture = textureSize.width / textureSize.height;
        float ratioPreview = previewSize.width / previewSize.height;
        if (ratioTexture < ratioPreview) {
            scaleX = ratioPreview / ratioTexture;
            scaleY = 1.0f;
        } else {
            scaleX = 1.0f;
            scaleY = ratioTexture / ratioPreview;
        }
        Matrix matrix = new Matrix();
        matrix.setScale(scaleX, scaleY);
        float scaledWidth = textureSize.width * scaleX;
        float scaledHeight = textureSize.height * scaleY;
        float dx = (textureSize.width - scaledWidth) / 2.0f;
        float dy = (textureSize.height - scaledHeight) / 2.0f;
        matrix.postTranslate(dx, dy);
        return matrix;
    }

    /* JADX INFO: Access modifiers changed from: private */
    public void startPreviewIfReady() {
        if (this.currentSurfaceSize != null && this.previewSize != null && this.surfaceRect != null) {
            if (this.surfaceView != null && this.currentSurfaceSize.equals(new Size(this.surfaceRect.width(), this.surfaceRect.height()))) {
                startCameraPreview(new CameraSurface(this.surfaceView.getHolder()));
                return;
            }
            if (this.textureView != null && this.textureView.getSurfaceTexture() != null) {
                if (this.previewSize != null) {
                    Matrix transform = calculateTextureTransform(new Size(this.textureView.getWidth(), this.textureView.getHeight()), this.previewSize);
                    this.textureView.setTransform(transform);
                }
                startCameraPreview(new CameraSurface(this.textureView.getSurfaceTexture()));
            }
        }
    }

    @Override // android.view.ViewGroup, android.view.View
    protected void onLayout(boolean changed, int l, int t, int r, int b) {
        containerSized(new Size(r - l, b - t));
        if (this.surfaceView != null) {
            if (this.surfaceRect == null) {
                this.surfaceView.layout(0, 0, getWidth(), getHeight());
                return;
            } else {
                this.surfaceView.layout(this.surfaceRect.left, this.surfaceRect.top, this.surfaceRect.right, this.surfaceRect.bottom);
                return;
            }
        }
        if (this.textureView != null) {
            this.textureView.layout(0, 0, getWidth(), getHeight());
        }
    }

    public Rect getFramingRect() {
        return this.framingRect;
    }

    public Rect getPreviewFramingRect() {
        return this.previewFramingRect;
    }

    public Size getPreviewSize() {
        return this.previewSize;
    }

    public CameraSettings getCameraSettings() {
        return this.cameraSettings;
    }

    public void setCameraSettings(CameraSettings cameraSettings) {
        this.cameraSettings = cameraSettings;
    }

    public void resume() {
        Util.validateMainThread();
        Log.d(TAG, "resume()");
        initCamera();
        if (this.currentSurfaceSize != null) {
            startPreviewIfReady();
        } else if (this.surfaceView != null) {
            this.surfaceView.getHolder().addCallback(this.surfaceCallback);
        } else if (this.textureView != null) {
            if (this.textureView.isAvailable()) {
                surfaceTextureListener().onSurfaceTextureAvailable(this.textureView.getSurfaceTexture(), this.textureView.getWidth(), this.textureView.getHeight());
            } else {
                this.textureView.setSurfaceTextureListener(surfaceTextureListener());
            }
        }
        requestLayout();
        this.rotationListener.listen(getContext(), this.rotationCallback);
    }

    public void pause() {
        Util.validateMainThread();
        Log.d(TAG, "pause()");
        this.openedOrientation = -1;
        if (this.cameraInstance != null) {
            this.cameraInstance.close();
            this.cameraInstance = null;
            this.previewActive = false;
        } else {
            this.stateHandler.sendEmptyMessage(R.id.zxing_camera_closed);
        }
        if (this.currentSurfaceSize == null && this.surfaceView != null) {
            SurfaceHolder surfaceHolder = this.surfaceView.getHolder();
            surfaceHolder.removeCallback(this.surfaceCallback);
        }
        if (this.currentSurfaceSize == null && this.textureView != null) {
            this.textureView.setSurfaceTextureListener(null);
        }
        this.containerSize = null;
        this.previewSize = null;
        this.previewFramingRect = null;
        this.rotationListener.stop();
        this.fireState.previewStopped();
    }

    public void pauseAndWait() {
        CameraInstance instance = getCameraInstance();
        pause();
        long startTime = System.nanoTime();
        while (instance != null && !instance.isCameraClosed() && System.nanoTime() - startTime <= 2000000000) {
            try {
                Thread.sleep(1L);
            } catch (InterruptedException e) {
                return;
            }
        }
    }

    public Size getFramingRectSize() {
        return this.framingRectSize;
    }

    public void setFramingRectSize(Size framingRectSize) {
        this.framingRectSize = framingRectSize;
    }

    public double getMarginFraction() {
        return this.marginFraction;
    }

    public void setMarginFraction(double marginFraction) {
        if (marginFraction >= 0.5d) {
            throw new IllegalArgumentException("The margin fraction must be less than 0.5");
        }
        this.marginFraction = marginFraction;
    }

    public boolean isUseTextureView() {
        return this.useTextureView;
    }

    public void setUseTextureView(boolean useTextureView) {
        this.useTextureView = useTextureView;
    }

    protected boolean isActive() {
        return this.cameraInstance != null;
    }

    private int getDisplayRotation() {
        return this.windowManager.getDefaultDisplay().getRotation();
    }

    private void initCamera() {
        if (this.cameraInstance != null) {
            Log.w(TAG, "initCamera called twice");
            return;
        }
        this.cameraInstance = createCameraInstance();
        this.cameraInstance.setReadyHandler(this.stateHandler);
        this.cameraInstance.open();
        this.openedOrientation = getDisplayRotation();
    }

    protected CameraInstance createCameraInstance() {
        CameraInstance cameraInstance = new CameraInstance(getContext());
        cameraInstance.setCameraSettings(this.cameraSettings);
        return cameraInstance;
    }

    private void startCameraPreview(CameraSurface surface) {
        if (!this.previewActive && this.cameraInstance != null) {
            Log.i(TAG, "Starting preview");
            this.cameraInstance.setSurface(surface);
            this.cameraInstance.startPreview();
            this.previewActive = true;
            previewStarted();
            this.fireState.previewStarted();
        }
    }

    protected void previewStarted() {
    }

    public CameraInstance getCameraInstance() {
        return this.cameraInstance;
    }

    public boolean isPreviewActive() {
        return this.previewActive;
    }

    protected Rect calculateFramingRect(Rect container, Rect surface) {
        Rect intersection = new Rect(container);
        intersection.intersect(surface);
        if (this.framingRectSize != null) {
            int horizontalMargin = Math.max(0, (intersection.width() - this.framingRectSize.width) / 2);
            int verticalMargin = Math.max(0, (intersection.height() - this.framingRectSize.height) / 2);
            intersection.inset(horizontalMargin, verticalMargin);
            return intersection;
        }
        int horizontalMargin2 = intersection.width();
        int margin = (int) Math.min(horizontalMargin2 * this.marginFraction, intersection.height() * this.marginFraction);
        intersection.inset(margin, margin);
        if (intersection.height() > intersection.width()) {
            intersection.inset(0, (intersection.height() - intersection.width()) / 2);
        }
        return intersection;
    }

    @Override // android.view.View
    protected Parcelable onSaveInstanceState() {
        Parcelable superState = super.onSaveInstanceState();
        Bundle myState = new Bundle();
        myState.putParcelable("super", superState);
        myState.putBoolean("torch", this.torchOn);
        return myState;
    }

    @Override // android.view.View
    protected void onRestoreInstanceState(Parcelable state) {
        if (!(state instanceof Bundle)) {
            super.onRestoreInstanceState(state);
            return;
        }
        Bundle myState = (Bundle) state;
        Parcelable superState = myState.getParcelable("super");
        super.onRestoreInstanceState(superState);
        boolean torch = myState.getBoolean("torch");
        setTorch(torch);
    }

    public boolean isCameraClosed() {
        return this.cameraInstance == null || this.cameraInstance.isCameraClosed();
    }
}
