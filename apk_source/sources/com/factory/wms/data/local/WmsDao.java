package com.factory.wms.data.local;

import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;

/* compiled from: WmsDao.kt */
@Metadata(d1 = {"\u00002\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0010\u0002\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000e\n\u0002\b\u0006\n\u0002\u0010\t\n\u0000\n\u0002\u0018\u0002\n\u0002\b\b\bg\u0018\u00002\u00020\u0001J\u001c\u0010\u0002\u001a\u00020\u00032\f\u0010\u0004\u001a\b\u0012\u0004\u0012\u00020\u00060\u0005H§@¢\u0006\u0002\u0010\u0007J\u001c\u0010\b\u001a\b\u0012\u0004\u0012\u00020\u00060\u00052\u0006\u0010\t\u001a\u00020\nH§@¢\u0006\u0002\u0010\u000bJ\u0018\u0010\f\u001a\u0004\u0018\u00010\u00062\u0006\u0010\r\u001a\u00020\nH§@¢\u0006\u0002\u0010\u000bJ\u0014\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\u00060\u0005H§@¢\u0006\u0002\u0010\u000fJ\u0016\u0010\u0010\u001a\u00020\u00112\u0006\u0010\u0012\u001a\u00020\u0013H§@¢\u0006\u0002\u0010\u0014J\u0014\u0010\u0015\u001a\b\u0012\u0004\u0012\u00020\u00130\u0005H§@¢\u0006\u0002\u0010\u000fJ\u001e\u0010\u0016\u001a\u00020\u00032\u0006\u0010\u0017\u001a\u00020\u00112\u0006\u0010\u0018\u001a\u00020\nH§@¢\u0006\u0002\u0010\u0019J\u0016\u0010\u001a\u001a\u00020\u00032\u0006\u0010\u0012\u001a\u00020\u0013H§@¢\u0006\u0002\u0010\u0014¨\u0006\u001b"}, d2 = {"Lcom/factory/wms/data/local/WmsDao;", "", "upsertMaterials", "", "materials", "", "Lcom/factory/wms/data/local/CachedMaterialEntity;", "(Ljava/util/List;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "searchMaterials", "keyword", "", "(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "materialByCode", "code", "allMaterials", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "insertPending", "", "document", "Lcom/factory/wms/data/local/PendingDocumentEntity;", "(Lcom/factory/wms/data/local/PendingDocumentEntity;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "pendingDocuments", "markPendingError", "id", "message", "(JLjava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "deletePending", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes8.dex */
public interface WmsDao {
    Object allMaterials(Continuation<? super List<CachedMaterialEntity>> continuation);

    Object deletePending(PendingDocumentEntity pendingDocumentEntity, Continuation<? super Unit> continuation);

    Object insertPending(PendingDocumentEntity pendingDocumentEntity, Continuation<? super Long> continuation);

    Object markPendingError(long j, String str, Continuation<? super Unit> continuation);

    Object materialByCode(String str, Continuation<? super CachedMaterialEntity> continuation);

    Object pendingDocuments(Continuation<? super List<PendingDocumentEntity>> continuation);

    Object searchMaterials(String str, Continuation<? super List<CachedMaterialEntity>> continuation);

    Object upsertMaterials(List<CachedMaterialEntity> list, Continuation<? super Unit> continuation);
}
