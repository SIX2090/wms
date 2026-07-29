package com.google.gson.internal.bind;

import com.google.gson.Gson;
import com.google.gson.JsonDeserializer;
import com.google.gson.JsonSerializer;
import com.google.gson.TypeAdapter;
import com.google.gson.TypeAdapterFactory;
import com.google.gson.annotations.JsonAdapter;
import com.google.gson.internal.ConstructorConstructor;
import com.google.gson.reflect.TypeToken;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/* loaded from: classes11.dex */
public final class JsonAdapterAnnotationTypeAdapterFactory implements TypeAdapterFactory {
    private static final TypeAdapterFactory TREE_TYPE_CLASS_DUMMY_FACTORY;
    private static final TypeAdapterFactory TREE_TYPE_FIELD_DUMMY_FACTORY;
    private final ConcurrentMap<Class<?>, TypeAdapterFactory> adapterFactoryMap = new ConcurrentHashMap();
    private final ConstructorConstructor constructorConstructor;

    private static class DummyTypeAdapterFactory implements TypeAdapterFactory {
        private DummyTypeAdapterFactory() {
        }

        @Override // com.google.gson.TypeAdapterFactory
        public <T> TypeAdapter<T> create(Gson gson, TypeToken<T> type) {
            throw new AssertionError("Factory should not be used");
        }
    }

    static {
        TREE_TYPE_CLASS_DUMMY_FACTORY = new DummyTypeAdapterFactory();
        TREE_TYPE_FIELD_DUMMY_FACTORY = new DummyTypeAdapterFactory();
    }

    public JsonAdapterAnnotationTypeAdapterFactory(ConstructorConstructor constructorConstructor) {
        this.constructorConstructor = constructorConstructor;
    }

    private static JsonAdapter getAnnotation(Class<?> rawType) {
        return (JsonAdapter) rawType.getAnnotation(JsonAdapter.class);
    }

    @Override // com.google.gson.TypeAdapterFactory
    public <T> TypeAdapter<T> create(Gson gson, TypeToken<T> typeToken) {
        JsonAdapter annotation = getAnnotation(typeToken.getRawType());
        if (annotation == null) {
            return null;
        }
        return (TypeAdapter<T>) getTypeAdapter(this.constructorConstructor, gson, typeToken, annotation, true);
    }

    private static Object createAdapter(ConstructorConstructor constructorConstructor, Class<?> adapterClass) {
        return constructorConstructor.get(TypeToken.get((Class) adapterClass)).construct();
    }

    private TypeAdapterFactory putFactoryAndGetCurrent(Class<?> rawType, TypeAdapterFactory factory) {
        TypeAdapterFactory existingFactory = this.adapterFactoryMap.putIfAbsent(rawType, factory);
        return existingFactory != null ? existingFactory : factory;
    }

    TypeAdapter<?> getTypeAdapter(ConstructorConstructor constructorConstructor, Gson gson, TypeToken<?> type, JsonAdapter annotation, boolean isClassAnnotation) {
        TypeAdapterFactory skipPast;
        TypeAdapter<?> typeAdapter;
        Object instance = createAdapter(constructorConstructor, annotation.value());
        boolean nullSafe = annotation.nullSafe();
        if (instance instanceof TypeAdapter) {
            typeAdapter = (TypeAdapter) instance;
        } else if (instance instanceof TypeAdapterFactory) {
            TypeAdapterFactory factory = (TypeAdapterFactory) instance;
            if (isClassAnnotation) {
                factory = putFactoryAndGetCurrent(type.getRawType(), factory);
            }
            typeAdapter = factory.create(gson, type);
        } else if ((instance instanceof JsonSerializer) || (instance instanceof JsonDeserializer)) {
            JsonSerializer<?> serializer = instance instanceof JsonSerializer ? (JsonSerializer) instance : null;
            JsonDeserializer<?> deserializer = instance instanceof JsonDeserializer ? (JsonDeserializer) instance : null;
            if (isClassAnnotation) {
                skipPast = TREE_TYPE_CLASS_DUMMY_FACTORY;
            } else {
                TypeAdapterFactory skipPast2 = TREE_TYPE_FIELD_DUMMY_FACTORY;
                skipPast = skipPast2;
            }
            typeAdapter = new TreeTypeAdapter<>(serializer, deserializer, gson, type, skipPast, nullSafe);
            nullSafe = false;
        } else {
            throw new IllegalArgumentException("Invalid attempt to bind an instance of " + instance.getClass().getName() + " as a @JsonAdapter for " + type.toString() + ". @JsonAdapter value must be a TypeAdapter, TypeAdapterFactory, JsonSerializer or JsonDeserializer.");
        }
        if (typeAdapter != null && nullSafe) {
            return typeAdapter.nullSafe();
        }
        return typeAdapter;
    }

    public boolean isClassJsonAdapterFactory(TypeToken<?> type, TypeAdapterFactory factory) {
        Objects.requireNonNull(type);
        Objects.requireNonNull(factory);
        if (factory == TREE_TYPE_CLASS_DUMMY_FACTORY) {
            return true;
        }
        Class<?> rawType = type.getRawType();
        TypeAdapterFactory existingFactory = this.adapterFactoryMap.get(rawType);
        if (existingFactory != null) {
            return existingFactory == factory;
        }
        JsonAdapter annotation = getAnnotation(rawType);
        if (annotation == null) {
            return false;
        }
        Class<?> adapterClass = annotation.value();
        if (!TypeAdapterFactory.class.isAssignableFrom(adapterClass)) {
            return false;
        }
        Object adapter = createAdapter(this.constructorConstructor, adapterClass);
        TypeAdapterFactory newFactory = (TypeAdapterFactory) adapter;
        return putFactoryAndGetCurrent(rawType, newFactory) == factory;
    }
}
