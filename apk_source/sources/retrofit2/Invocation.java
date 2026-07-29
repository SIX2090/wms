package retrofit2;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import javax.annotation.Nullable;

/* loaded from: classes11.dex */
public final class Invocation {
    private final List<?> arguments;

    @Nullable
    private final Object instance;
    private final Method method;
    private final Class<?> service;

    public static <T> Invocation of(Class<T> service, T instance, Method method, List<?> arguments) {
        Objects.requireNonNull(service, "service == null");
        Objects.requireNonNull(instance, "instance == null");
        Objects.requireNonNull(method, "method == null");
        Objects.requireNonNull(arguments, "arguments == null");
        return new Invocation(service, instance, method, new ArrayList(arguments));
    }

    @Deprecated
    public static Invocation of(Method method, List<?> arguments) {
        Objects.requireNonNull(method, "method == null");
        Objects.requireNonNull(arguments, "arguments == null");
        return new Invocation(method.getDeclaringClass(), null, method, new ArrayList(arguments));
    }

    Invocation(Class<?> service, @Nullable Object instance, Method method, List<?> arguments) {
        this.service = service;
        this.instance = instance;
        this.method = method;
        this.arguments = Collections.unmodifiableList(arguments);
    }

    public Class<?> service() {
        return this.service;
    }

    @Nullable
    public Object instance() {
        return this.instance;
    }

    public Method method() {
        return this.method;
    }

    public List<?> arguments() {
        return this.arguments;
    }

    public String toString() {
        return String.format("%s.%s() %s", this.service.getName(), this.method.getName(), this.arguments);
    }
}
