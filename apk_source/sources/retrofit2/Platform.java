package retrofit2;

import java.util.concurrent.Executor;
import javax.annotation.Nullable;
import retrofit2.BuiltInFactories;
import retrofit2.Reflection;

/* loaded from: classes11.dex */
final class Platform {
    static final BuiltInFactories builtInFactories;

    @Nullable
    static final Executor callbackExecutor;
    static final Reflection reflection;

    /* JADX WARN: Can't fix incorrect switch cases order, some code will duplicate */
    static {
        char c;
        String property = System.getProperty("java.vm.name");
        switch (property.hashCode()) {
            case -1841837151:
                if (property.equals("RoboVM")) {
                    c = 1;
                    break;
                }
                c = 65535;
                break;
            case 2039697993:
                if (property.equals("Dalvik")) {
                    c = 0;
                    break;
                }
                c = 65535;
                break;
            default:
                c = 65535;
                break;
        }
        switch (c) {
            case 0:
                callbackExecutor = new AndroidMainExecutor();
                reflection = new Reflection.Android24();
                builtInFactories = new BuiltInFactories.Java8();
                break;
            case 1:
                callbackExecutor = null;
                reflection = new Reflection();
                builtInFactories = new BuiltInFactories();
                break;
            default:
                callbackExecutor = null;
                reflection = new Reflection.Java8();
                builtInFactories = new BuiltInFactories.Java8();
                break;
        }
    }

    private Platform() {
    }
}
