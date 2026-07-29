package retrofit2;

import java.lang.reflect.Method;
import java.lang.reflect.Parameter;
import javax.annotation.Nullable;

/* loaded from: classes11.dex */
class Reflection {
    Reflection() {
    }

    boolean isDefaultMethod(Method method) {
        return false;
    }

    @Nullable
    Object invokeDefaultMethod(Method method, Class<?> declaringClass, Object proxy, @Nullable Object[] args) throws Throwable {
        throw new AssertionError();
    }

    String describeMethodParameter(Method method, int index) {
        return "parameter #" + (index + 1);
    }

    static class Java8 extends Reflection {
        Java8() {
        }

        @Override // retrofit2.Reflection
        boolean isDefaultMethod(Method method) {
            return method.isDefault();
        }

        @Override // retrofit2.Reflection
        Object invokeDefaultMethod(Method method, Class<?> declaringClass, Object proxy, @Nullable Object[] args) throws Throwable {
            return DefaultMethodSupport.invoke(method, declaringClass, proxy, args);
        }

        @Override // retrofit2.Reflection
        String describeMethodParameter(Method method, int index) {
            Parameter parameter = method.getParameters()[index];
            if (parameter.isNamePresent()) {
                return "parameter '" + parameter.getName() + '\'';
            }
            return super.describeMethodParameter(method, index);
        }
    }

    static final class Android24 extends Reflection {
        Android24() {
        }

        @Override // retrofit2.Reflection
        boolean isDefaultMethod(Method method) {
            return method.isDefault();
        }

        @Override // retrofit2.Reflection
        Object invokeDefaultMethod(Method method, Class<?> declaringClass, Object proxy, @Nullable Object[] args) throws Throwable {
            return DefaultMethodSupport.invoke(method, declaringClass, proxy, args);
        }
    }
}
