package com.factory.wms.data.repository;

import com.factory.wms.data.api.WmsApiService;
import com.factory.wms.data.local.WmsDao;
import com.factory.wms.data.model.InboundLineDto;
import com.factory.wms.data.model.InboundRequest;
import com.factory.wms.data.model.OutboundLineDto;
import com.factory.wms.data.model.OutboundRequest;
import com.factory.wms.data.model.StocktakeLineDto;
import com.factory.wms.data.model.StocktakeRequest;
import com.google.gson.Gson;
import java.util.List;
import kotlin.Metadata;
import kotlin.Unit;
import kotlin.coroutines.Continuation;
import kotlin.jvm.internal.Intrinsics;

/* compiled from: WmsRepository.kt */
@Metadata(d1 = {"\u0000j\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0002\b\u0003\n\u0002\u0010\u000e\n\u0002\b\u0004\n\u0002\u0010\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0002\b\u0004\n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\b\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\b\u0007\u0018\u00002\u00020\u0001B\u0017\u0012\u0006\u0010\u0002\u001a\u00020\u0003\u0012\u0006\u0010\u0004\u001a\u00020\u0005¢\u0006\u0004\b\u0006\u0010\u0007J\u001a\u0010\n\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\r0\f0\u000bH\u0086@¢\u0006\u0002\u0010\u000eJ\"\u0010\u000f\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\r0\f0\u000b2\u0006\u0010\u0010\u001a\u00020\u0011H\u0086@¢\u0006\u0002\u0010\u0012J\u0018\u0010\u0013\u001a\u0004\u0018\u00010\r2\u0006\u0010\u0014\u001a\u00020\u0011H\u0086@¢\u0006\u0002\u0010\u0012J\"\u0010\u0015\u001a\b\u0012\u0004\u0012\u00020\u00160\u000b2\f\u0010\u0017\u001a\b\u0012\u0004\u0012\u00020\u00180\fH\u0086@¢\u0006\u0002\u0010\u0019J6\u0010\u001a\u001a\b\u0012\u0004\u0012\u00020\u00160\u000b2\b\u0010\u001b\u001a\u0004\u0018\u00010\u00112\b\u0010\u001c\u001a\u0004\u0018\u00010\u00112\f\u0010\u0017\u001a\b\u0012\u0004\u0012\u00020\u001d0\fH\u0086@¢\u0006\u0002\u0010\u001eJ4\u0010\u001f\u001a\b\u0012\u0004\u0012\u00020\u00160\u000b2\u0006\u0010 \u001a\u00020\u00112\b\u0010!\u001a\u0004\u0018\u00010\u00112\f\u0010\u0017\u001a\b\u0012\u0004\u0012\u00020\"0\fH\u0086@¢\u0006\u0002\u0010\u001eJ\u000e\u0010#\u001a\u00020$H\u0086@¢\u0006\u0002\u0010\u000eJ\u000e\u0010%\u001a\u00020$H\u0086@¢\u0006\u0002\u0010\u000eJL\u0010&\u001a\b\u0012\u0004\u0012\u00020\u00160\u000b\"\u0004\b\u0000\u0010'2\u0006\u0010(\u001a\u00020\u00112\u0006\u0010)\u001a\u0002H'2 \u0010*\u001a\u001c\b\u0001\u0012\u000e\u0012\f\u0012\b\u0012\u0006\u0012\u0002\b\u00030-0,\u0012\u0006\u0012\u0004\u0018\u00010\u00010+H\u0082@¢\u0006\u0002\u0010.R\u000e\u0010\u0002\u001a\u00020\u0003X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\u0004\u001a\u00020\u0005X\u0082\u0004¢\u0006\u0002\n\u0000R\u000e\u0010\b\u001a\u00020\tX\u0082\u0004¢\u0006\u0002\n\u0000¨\u0006/"}, d2 = {"Lcom/factory/wms/data/repository/WmsRepository;", "", "api", "Lcom/factory/wms/data/api/WmsApiService;", "dao", "Lcom/factory/wms/data/local/WmsDao;", "<init>", "(Lcom/factory/wms/data/api/WmsApiService;Lcom/factory/wms/data/local/WmsDao;)V", "gson", "Lcom/google/gson/Gson;", "refreshMaterials", "Lcom/factory/wms/data/repository/NetworkResult;", "", "Lcom/factory/wms/data/model/MaterialDto;", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "findMaterial", "codeOrKeyword", "", "(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "materialByCode", "code", "submitInbound", "", "lines", "Lcom/factory/wms/data/model/InboundLineDto;", "(Ljava/util/List;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "submitOutbound", "receiver", "department", "Lcom/factory/wms/data/model/OutboundLineDto;", "(Ljava/lang/String;Ljava/lang/String;Ljava/util/List;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "submitStocktake", "mode", "warehouseCode", "Lcom/factory/wms/data/model/StocktakeLineDto;", "retryPending", "", "pendingCount", "submitOrCache", "T", "type", "request", "block", "Lkotlin/Function1;", "Lkotlin/coroutines/Continuation;", "Lcom/factory/wms/data/model/ApiEnvelope;", "(Ljava/lang/String;Ljava/lang/Object;Lkotlin/jvm/functions/Function1;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes6.dex */
public final class WmsRepository {
    public static final int $stable = 8;
    private final WmsApiService api;
    private final WmsDao dao;
    private final Gson gson;

    public WmsRepository(WmsApiService api, WmsDao dao) {
        Intrinsics.checkNotNullParameter(api, "api");
        Intrinsics.checkNotNullParameter(dao, "dao");
        this.api = api;
        this.dao = dao;
        this.gson = new Gson();
    }

    /* JADX WARN: Can't wrap try/catch for region: R(7:0|1|(2:3|(4:5|6|7|8))|57|6|7|8) */
    /* JADX WARN: Code restructure failed: missing block: B:53:0x00d7, code lost:
    
        r0 = e;
     */
    /* JADX WARN: Code restructure failed: missing block: B:54:0x00d8, code lost:
    
        r6 = r7.dao;
        r3.L$0 = r0;
        r3.L$1 = null;
        r3.label = 3;
        r6 = r6.allMaterials(r3);
     */
    /* JADX WARN: Code restructure failed: missing block: B:55:0x00e6, code lost:
    
        if (r6 == r5) goto L41;
     */
    /* JADX WARN: Code restructure failed: missing block: B:56:0x00e8, code lost:
    
        return r5;
     */
    /* JADX WARN: Not initialized variable reg: 7, insn: 0x00d8: IGET (r6 I:com.factory.wms.data.local.WmsDao) = (r7 I:com.factory.wms.data.repository.WmsRepository A[D('this' com.factory.wms.data.repository.WmsRepository)]) (LINE:33) com.factory.wms.data.repository.WmsRepository.dao com.factory.wms.data.local.WmsDao, block:B:54:0x00d8 */
    /* JADX WARN: Removed duplicated region for block: B:12:0x0035  */
    /* JADX WARN: Removed duplicated region for block: B:27:0x003f  */
    /* JADX WARN: Removed duplicated region for block: B:31:0x004c  */
    /* JADX WARN: Removed duplicated region for block: B:36:0x0072 A[Catch: Exception -> 0x00d7, TryCatch #0 {Exception -> 0x00d7, blocks: (B:28:0x0047, B:29:0x00c0, B:32:0x0051, B:34:0x006a, B:36:0x0072, B:38:0x007a, B:39:0x007e, B:40:0x0095, B:42:0x009b, B:44:0x00ad, B:47:0x00ca, B:50:0x005c), top: B:7:0x002a }] */
    /* JADX WARN: Removed duplicated region for block: B:47:0x00ca A[Catch: Exception -> 0x00d7, TRY_LEAVE, TryCatch #0 {Exception -> 0x00d7, blocks: (B:28:0x0047, B:29:0x00c0, B:32:0x0051, B:34:0x006a, B:36:0x0072, B:38:0x007a, B:39:0x007e, B:40:0x0095, B:42:0x009b, B:44:0x00ad, B:47:0x00ca, B:50:0x005c), top: B:7:0x002a }] */
    /* JADX WARN: Removed duplicated region for block: B:49:0x0056  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x002d  */
    /* JADX WARN: Type inference failed for: r7v0, types: [com.factory.wms.data.repository.WmsRepository] */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object refreshMaterials(kotlin.coroutines.Continuation<? super com.factory.wms.data.repository.NetworkResult<? extends java.util.List<com.factory.wms.data.model.MaterialDto>>> r17) {
        /*
            Method dump skipped, instructions count: 334
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.WmsRepository.refreshMaterials(kotlin.coroutines.Continuation):java.lang.Object");
    }

    /* JADX WARN: Can't wrap try/catch for region: R(7:0|1|(2:3|(4:5|6|7|8))|57|6|7|8) */
    /* JADX WARN: Code restructure failed: missing block: B:54:0x0102, code lost:
    
        r0 = r10.dao;
        r3.L$0 = null;
        r3.L$1 = null;
        r3.L$2 = null;
        r3.label = 3;
        r0 = r0.searchMaterials(r9, r3);
     */
    /* JADX WARN: Code restructure failed: missing block: B:55:0x0111, code lost:
    
        if (r0 == r5) goto L45;
     */
    /* JADX WARN: Code restructure failed: missing block: B:56:0x0113, code lost:
    
        return r5;
     */
    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Not initialized variable reg: 10, insn: 0x0102: IGET (r0 I:com.factory.wms.data.local.WmsDao) = (r10 I:com.factory.wms.data.repository.WmsRepository A[D('this' com.factory.wms.data.repository.WmsRepository)]) (LINE:55) com.factory.wms.data.repository.WmsRepository.dao com.factory.wms.data.local.WmsDao, block:B:54:0x0102 */
    /* JADX WARN: Not initialized variable reg: 9, insn: 0x010d: INVOKE (r0 I:java.lang.Object) = 
      (r0v5 ?? I:com.factory.wms.data.local.WmsDao)
      (r9 I:java.lang.String A[D('keyword' java.lang.String)])
      (r3 I:kotlin.coroutines.Continuation A[D('$continuation' kotlin.coroutines.Continuation)])
     INTERFACE call: com.factory.wms.data.local.WmsDao.searchMaterials(java.lang.String, kotlin.coroutines.Continuation):java.lang.Object A[MD:(java.lang.String, kotlin.coroutines.Continuation<? super java.util.List<com.factory.wms.data.local.CachedMaterialEntity>>):java.lang.Object (m)], block:B:54:0x0102 */
    /* JADX WARN: Removed duplicated region for block: B:12:0x0037  */
    /* JADX WARN: Removed duplicated region for block: B:24:0x003d  */
    /* JADX WARN: Removed duplicated region for block: B:28:0x004e  */
    /* JADX WARN: Removed duplicated region for block: B:33:0x009b A[Catch: Exception -> 0x0101, TryCatch #0 {Exception -> 0x0101, blocks: (B:25:0x0049, B:26:0x00ec, B:29:0x0058, B:31:0x0093, B:33:0x009b, B:35:0x00a3, B:36:0x00a7, B:37:0x00be, B:39:0x00c4, B:41:0x00d8, B:44:0x00f4, B:50:0x0083), top: B:7:0x002c }] */
    /* JADX WARN: Removed duplicated region for block: B:44:0x00f4 A[Catch: Exception -> 0x0101, TRY_LEAVE, TryCatch #0 {Exception -> 0x0101, blocks: (B:25:0x0049, B:26:0x00ec, B:29:0x0058, B:31:0x0093, B:33:0x009b, B:35:0x00a3, B:36:0x00a7, B:37:0x00be, B:39:0x00c4, B:41:0x00d8, B:44:0x00f4, B:50:0x0083), top: B:7:0x002c }] */
    /* JADX WARN: Removed duplicated region for block: B:46:0x005d  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x002f  */
    /* JADX WARN: Type inference failed for: r10v0, types: [com.factory.wms.data.repository.WmsRepository] */
    /* JADX WARN: Type inference failed for: r9v0, types: [java.lang.String] */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object findMaterial(java.lang.String r20, kotlin.coroutines.Continuation<? super com.factory.wms.data.repository.NetworkResult<? extends java.util.List<com.factory.wms.data.model.MaterialDto>>> r21) {
        /*
            Method dump skipped, instructions count: 370
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.WmsRepository.findMaterial(java.lang.String, kotlin.coroutines.Continuation):java.lang.Object");
    }

    /* JADX WARN: Can't wrap try/catch for region: R(7:0|1|(2:3|(4:5|6|7|8))|59|6|7|8) */
    /* JADX WARN: Multi-variable type inference failed */
    /* JADX WARN: Removed duplicated region for block: B:12:0x002d  */
    /* JADX WARN: Removed duplicated region for block: B:15:0x00fb  */
    /* JADX WARN: Removed duplicated region for block: B:17:? A[RETURN, SYNTHETIC] */
    /* JADX WARN: Removed duplicated region for block: B:18:0x0033  */
    /* JADX WARN: Removed duplicated region for block: B:23:0x00dc A[Catch: Exception -> 0x00e4, TRY_LEAVE, TryCatch #0 {Exception -> 0x00e4, blocks: (B:19:0x003b, B:21:0x00d8, B:23:0x00dc, B:39:0x005f, B:41:0x008e, B:43:0x0096, B:45:0x009c, B:49:0x00c8, B:55:0x007e), top: B:7:0x0022 }] */
    /* JADX WARN: Removed duplicated region for block: B:26:0x0041  */
    /* JADX WARN: Removed duplicated region for block: B:38:0x0057  */
    /* JADX WARN: Removed duplicated region for block: B:51:0x00d7 A[RETURN] */
    /* JADX WARN: Removed duplicated region for block: B:52:0x0064  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x0025  */
    /* JADX WARN: Type inference failed for: r3v0, types: [int] */
    /* JADX WARN: Type inference failed for: r3v8 */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object materialByCode(java.lang.String r11, kotlin.coroutines.Continuation<? super com.factory.wms.data.model.MaterialDto> r12) {
        /*
            Method dump skipped, instructions count: 270
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.WmsRepository.materialByCode(java.lang.String, kotlin.coroutines.Continuation):java.lang.Object");
    }

    public final Object submitInbound(List<InboundLineDto> list, Continuation<? super NetworkResult<Unit>> continuation) {
        InboundRequest request = new InboundRequest(list);
        return submitOrCache("inbound", request, new WmsRepository$submitInbound$2(this, request, null), continuation);
    }

    public final Object submitOutbound(String receiver, String department, List<OutboundLineDto> list, Continuation<? super NetworkResult<Unit>> continuation) {
        OutboundRequest request = new OutboundRequest(receiver, department, list);
        return submitOrCache("outbound", request, new WmsRepository$submitOutbound$2(this, request, null), continuation);
    }

    public final Object submitStocktake(String mode, String warehouseCode, List<StocktakeLineDto> list, Continuation<? super NetworkResult<Unit>> continuation) {
        StocktakeRequest request = new StocktakeRequest(mode, warehouseCode, list);
        return submitOrCache("stocktake", request, new WmsRepository$submitStocktake$2(this, request, null), continuation);
    }

    /* JADX WARN: Can't fix incorrect switch cases order, some code will duplicate */
    /* JADX WARN: Can't wrap try/catch for region: R(7:0|1|(2:3|(4:5|6|7|8))|99|6|7|8) */
    /* JADX WARN: Can't wrap try/catch for region: R(7:34|35|36|37|38|13|(0)(0)) */
    /* JADX WARN: Code restructure failed: missing block: B:40:0x01e0, code lost:
    
        r3 = move-exception;
     */
    /* JADX WARN: Code restructure failed: missing block: B:41:0x01e1, code lost:
    
        r8 = r3;
        r3 = r8;
     */
    /* JADX WARN: Code restructure failed: missing block: B:44:0x021b, code lost:
    
        r5 = "重传失败";
     */
    /* JADX WARN: Code restructure failed: missing block: B:47:0x022e, code lost:
    
        return r2;
     */
    /* JADX WARN: Code restructure failed: missing block: B:98:0x00af, code lost:
    
        r8 = e;
     */
    /* JADX WARN: Removed duplicated region for block: B:12:0x002d  */
    /* JADX WARN: Removed duplicated region for block: B:15:0x00e0  */
    /* JADX WARN: Removed duplicated region for block: B:29:0x01b8 A[Catch: Exception -> 0x0130, TryCatch #1 {Exception -> 0x0130, blocks: (B:27:0x012c, B:29:0x01b8, B:31:0x01be, B:48:0x01e5, B:50:0x01ed, B:52:0x01f5, B:67:0x0171, B:75:0x01ab), top: B:26:0x012c }] */
    /* JADX WARN: Removed duplicated region for block: B:44:0x021b  */
    /* JADX WARN: Removed duplicated region for block: B:47:0x022e A[RETURN] */
    /* JADX WARN: Removed duplicated region for block: B:50:0x01ed A[Catch: Exception -> 0x0130, TryCatch #1 {Exception -> 0x0130, blocks: (B:27:0x012c, B:29:0x01b8, B:31:0x01be, B:48:0x01e5, B:50:0x01ed, B:52:0x01f5, B:67:0x0171, B:75:0x01ab), top: B:26:0x012c }] */
    /* JADX WARN: Removed duplicated region for block: B:54:0x0206 A[RETURN] */
    /* JADX WARN: Removed duplicated region for block: B:55:0x0207  */
    /* JADX WARN: Removed duplicated region for block: B:78:0x0231  */
    /* JADX WARN: Removed duplicated region for block: B:80:0x003e  */
    /* JADX WARN: Removed duplicated region for block: B:82:0x0051  */
    /* JADX WARN: Removed duplicated region for block: B:84:0x0064  */
    /* JADX WARN: Removed duplicated region for block: B:87:0x007d  */
    /* JADX WARN: Removed duplicated region for block: B:90:0x0096  */
    /* JADX WARN: Removed duplicated region for block: B:93:0x00b2  */
    /* JADX WARN: Removed duplicated region for block: B:95:0x00bd  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x0025  */
    /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:38:0x01dd -> B:13:0x00da). Please report as a decompilation issue!!! */
    /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:46:0x022c -> B:13:0x00da). Please report as a decompilation issue!!! */
    /* JADX WARN: Unsupported multi-entry loop pattern (BACK_EDGE: B:55:0x0207 -> B:13:0x00da). Please report as a decompilation issue!!! */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object retryPending(kotlin.coroutines.Continuation<? super java.lang.Integer> r15) {
        /*
            Method dump skipped, instructions count: 600
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.WmsRepository.retryPending(kotlin.coroutines.Continuation):java.lang.Object");
    }

    /* JADX WARN: Removed duplicated region for block: B:11:0x002c  */
    /* JADX WARN: Removed duplicated region for block: B:14:0x0031  */
    /* JADX WARN: Removed duplicated region for block: B:8:0x0024  */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final java.lang.Object pendingCount(kotlin.coroutines.Continuation<? super java.lang.Integer> r7) {
        /*
            r6 = this;
            boolean r0 = r7 instanceof com.factory.wms.data.repository.WmsRepository$pendingCount$1
            if (r0 == 0) goto L14
            r0 = r7
            com.factory.wms.data.repository.WmsRepository$pendingCount$1 r0 = (com.factory.wms.data.repository.WmsRepository$pendingCount$1) r0
            int r1 = r0.label
            r2 = -2147483648(0xffffffff80000000, float:-0.0)
            r1 = r1 & r2
            if (r1 == 0) goto L14
            int r1 = r0.label
            int r1 = r1 - r2
            r0.label = r1
            goto L19
        L14:
            com.factory.wms.data.repository.WmsRepository$pendingCount$1 r0 = new com.factory.wms.data.repository.WmsRepository$pendingCount$1
            r0.<init>(r6, r7)
        L19:
            java.lang.Object r1 = r0.result
            java.lang.Object r2 = kotlin.coroutines.intrinsics.IntrinsicsKt.getCOROUTINE_SUSPENDED()
            int r3 = r0.label
            switch(r3) {
                case 0: goto L31;
                case 1: goto L2c;
                default: goto L24;
            }
        L24:
            java.lang.IllegalStateException r0 = new java.lang.IllegalStateException
            java.lang.String r1 = "call to 'resume' before 'invoke' with coroutine"
            r0.<init>(r1)
            throw r0
        L2c:
            kotlin.ResultKt.throwOnFailure(r1)
            r3 = r1
            goto L41
        L31:
            kotlin.ResultKt.throwOnFailure(r1)
            r3 = r6
            com.factory.wms.data.local.WmsDao r4 = r3.dao
            r5 = 1
            r0.label = r5
            java.lang.Object r3 = r4.pendingDocuments(r0)
            if (r3 != r2) goto L41
            return r2
        L41:
            java.util.List r3 = (java.util.List) r3
            int r2 = r3.size()
            java.lang.Integer r2 = kotlin.coroutines.jvm.internal.Boxing.boxInt(r2)
            return r2
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.WmsRepository.pendingCount(kotlin.coroutines.Continuation):java.lang.Object");
    }

    /* JADX INFO: Access modifiers changed from: private */
    /* JADX WARN: Can't wrap try/catch for region: R(7:0|1|(2:3|(4:5|6|7|8))|32|6|7|8) */
    /* JADX WARN: Code restructure failed: missing block: B:28:0x0089, code lost:
    
        r0 = move-exception;
     */
    /* JADX WARN: Code restructure failed: missing block: B:29:0x008a, code lost:
    
        r15 = r8.dao;
        r11 = r8.gson.toJson(r6);
        kotlin.jvm.internal.Intrinsics.checkNotNullExpressionValue(r11, "toJson(...)");
        r14 = new com.factory.wms.data.local.PendingDocumentEntity(0, r7, r11, java.lang.System.currentTimeMillis(), r0.getMessage(), 1, null);
        r3.L$0 = null;
        r3.L$1 = null;
        r3.L$2 = null;
        r3.label = 2;
     */
    /* JADX WARN: Code restructure failed: missing block: B:30:0x00c1, code lost:
    
        if (r15.insertPending(r14, r3) == r5) goto L28;
     */
    /* JADX WARN: Code restructure failed: missing block: B:31:0x00c3, code lost:
    
        return r5;
     */
    /* JADX WARN: Failed to apply debug info
    java.lang.NullPointerException: Cannot invoke "jadx.core.dex.instructions.args.InsnArg.getType()" because "changeArg" is null
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.moveListener(TypeUpdate.java:439)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.runListeners(TypeUpdate.java:232)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.requestUpdate(TypeUpdate.java:212)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeForSsaVar(TypeUpdate.java:183)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeChecked(TypeUpdate.java:112)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.apply(TypeUpdate.java:83)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.applyWithWiderIgnoreUnknown(TypeUpdate.java:74)
    	at jadx.core.dex.visitors.debuginfo.DebugInfoApplyVisitor.applyDebugInfo(DebugInfoApplyVisitor.java:137)
    	at jadx.core.dex.visitors.debuginfo.DebugInfoApplyVisitor.applyDebugInfo(DebugInfoApplyVisitor.java:133)
    	at jadx.core.dex.visitors.debuginfo.DebugInfoApplyVisitor.searchAndApplyVarDebugInfo(DebugInfoApplyVisitor.java:75)
    	at jadx.core.dex.visitors.debuginfo.DebugInfoApplyVisitor.lambda$applyDebugInfo$0(DebugInfoApplyVisitor.java:68)
    	at java.base/java.util.ArrayList.forEach(ArrayList.java:1604)
    	at jadx.core.dex.visitors.debuginfo.DebugInfoApplyVisitor.applyDebugInfo(DebugInfoApplyVisitor.java:68)
    	at jadx.core.dex.visitors.debuginfo.DebugInfoApplyVisitor.visit(DebugInfoApplyVisitor.java:55)
     */
    /* JADX WARN: Failed to calculate best type for var: r7v0 ??
    java.lang.NullPointerException: Cannot invoke "jadx.core.dex.instructions.args.InsnArg.getType()" because "changeArg" is null
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.moveListener(TypeUpdate.java:439)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.runListeners(TypeUpdate.java:232)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.requestUpdate(TypeUpdate.java:212)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeForSsaVar(TypeUpdate.java:183)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeChecked(TypeUpdate.java:112)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.apply(TypeUpdate.java:83)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.apply(TypeUpdate.java:56)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.calculateFromBounds(FixTypesVisitor.java:156)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.setBestType(FixTypesVisitor.java:133)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.deduceType(FixTypesVisitor.java:238)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.tryDeduceTypes(FixTypesVisitor.java:221)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.visit(FixTypesVisitor.java:91)
     */
    /* JADX WARN: Failed to calculate best type for var: r7v0 ??
    java.lang.NullPointerException: Cannot invoke "jadx.core.dex.instructions.args.InsnArg.getType()" because "changeArg" is null
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.moveListener(TypeUpdate.java:439)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.runListeners(TypeUpdate.java:232)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.requestUpdate(TypeUpdate.java:212)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeForSsaVar(TypeUpdate.java:183)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeChecked(TypeUpdate.java:112)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.apply(TypeUpdate.java:83)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.apply(TypeUpdate.java:56)
    	at jadx.core.dex.visitors.typeinference.TypeInferenceVisitor.calculateFromBounds(TypeInferenceVisitor.java:145)
    	at jadx.core.dex.visitors.typeinference.TypeInferenceVisitor.setBestType(TypeInferenceVisitor.java:123)
    	at jadx.core.dex.visitors.typeinference.TypeInferenceVisitor.lambda$runTypePropagation$2(TypeInferenceVisitor.java:101)
    	at java.base/java.util.ArrayList.forEach(ArrayList.java:1604)
    	at jadx.core.dex.visitors.typeinference.TypeInferenceVisitor.runTypePropagation(TypeInferenceVisitor.java:101)
    	at jadx.core.dex.visitors.typeinference.TypeInferenceVisitor.visit(TypeInferenceVisitor.java:75)
     */
    /* JADX WARN: Multi-variable type inference failed. Error: java.lang.NullPointerException: Cannot invoke "jadx.core.dex.instructions.args.InsnArg.getType()" because "changeArg" is null
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.moveListener(TypeUpdate.java:439)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.runListeners(TypeUpdate.java:232)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.requestUpdate(TypeUpdate.java:212)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeForSsaVar(TypeUpdate.java:183)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.updateTypeChecked(TypeUpdate.java:112)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.apply(TypeUpdate.java:83)
    	at jadx.core.dex.visitors.typeinference.TypeUpdate.applyWithWiderIgnSame(TypeUpdate.java:70)
    	at jadx.core.dex.visitors.typeinference.TypeSearch.applyResolvedVars(TypeSearch.java:100)
    	at jadx.core.dex.visitors.typeinference.TypeSearch.run(TypeSearch.java:76)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.runMultiVariableSearch(FixTypesVisitor.java:116)
    	at jadx.core.dex.visitors.typeinference.FixTypesVisitor.visit(FixTypesVisitor.java:91)
     */
    /* JADX WARN: Not initialized variable reg: 6, insn: 0x0092: INVOKE (r11 I:java.lang.String) = (r7v1 ?? I:com.google.gson.Gson), (r6 I:java.lang.Object A[D('request' java.lang.Object)]) VIRTUAL call: com.google.gson.Gson.toJson(java.lang.Object):java.lang.String A[MD:(java.lang.Object):java.lang.String (m)], block:B:29:0x008a */
    /* JADX WARN: Not initialized variable reg: 7, insn: 0x008a: MOVE (r10 I:??[OBJECT, ARRAY]) = (r7 I:??[OBJECT, ARRAY] A[D('type' java.lang.String)]), block:B:29:0x008a */
    /* JADX WARN: Not initialized variable reg: 8, insn: 0x008b: IGET (r15 I:com.factory.wms.data.local.WmsDao) = (r8 I:com.factory.wms.data.repository.WmsRepository A[D('this' com.factory.wms.data.repository.WmsRepository)]) (LINE:140) com.factory.wms.data.repository.WmsRepository.dao com.factory.wms.data.local.WmsDao, block:B:29:0x008a */
    /* JADX WARN: Removed duplicated region for block: B:12:0x0033  */
    /* JADX WARN: Removed duplicated region for block: B:15:0x0038  */
    /* JADX WARN: Removed duplicated region for block: B:20:0x006e A[Catch: Exception -> 0x0089, TryCatch #0 {Exception -> 0x0089, blocks: (B:16:0x0044, B:18:0x0065, B:20:0x006e, B:22:0x007c, B:25:0x0055), top: B:7:0x0028 }] */
    /* JADX WARN: Removed duplicated region for block: B:22:0x007c A[Catch: Exception -> 0x0089, TRY_LEAVE, TryCatch #0 {Exception -> 0x0089, blocks: (B:16:0x0044, B:18:0x0065, B:20:0x006e, B:22:0x007c, B:25:0x0055), top: B:7:0x0028 }] */
    /* JADX WARN: Removed duplicated region for block: B:24:0x0049  */
    /* JADX WARN: Removed duplicated region for block: B:9:0x002b  */
    /* JADX WARN: Type inference failed for: r8v0, names: [this], types: [com.factory.wms.data.repository.WmsRepository] */
    /*
        Code decompiled incorrectly, please refer to instructions dump.
        To view partially-correct add '--show-bad-code' argument
    */
    public final <T> java.lang.Object submitOrCache(java.lang.String r19, T r20, kotlin.jvm.functions.Function1<? super kotlin.coroutines.Continuation<? super com.factory.wms.data.model.ApiEnvelope<?>>, ? extends java.lang.Object> r21, kotlin.coroutines.Continuation<? super com.factory.wms.data.repository.NetworkResult<kotlin.Unit>> r22) {
        /*
            Method dump skipped, instructions count: 220
            To view this dump add '--comments-level debug' option
        */
        throw new UnsupportedOperationException("Method not decompiled: com.factory.wms.data.repository.WmsRepository.submitOrCache(java.lang.String, java.lang.Object, kotlin.jvm.functions.Function1, kotlin.coroutines.Continuation):java.lang.Object");
    }
}
