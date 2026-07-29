package com.factory.wms.data.api;

import com.factory.wms.data.model.ApiEnvelope;
import com.factory.wms.data.model.InboundRequest;
import com.factory.wms.data.model.LoginData;
import com.factory.wms.data.model.LoginRequest;
import com.factory.wms.data.model.MaterialDto;
import com.factory.wms.data.model.OutboundRequest;
import com.factory.wms.data.model.StocktakeRequest;
import com.factory.wms.data.model.SubmitResult;
import java.util.List;
import kotlin.Metadata;
import kotlin.coroutines.Continuation;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;
import retrofit2.http.Query;

/* compiled from: WmsApiService.kt */
@Metadata(d1 = {"\u0000J\n\u0002\u0018\u0002\n\u0002\u0010\u0000\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0010\u000e\n\u0002\b\u0006\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\bf\u0018\u00002\u00020\u0001J\u001e\u0010\u0002\u001a\b\u0012\u0004\u0012\u00020\u00040\u00032\b\b\u0001\u0010\u0005\u001a\u00020\u0006H§@¢\u0006\u0002\u0010\u0007J$\u0010\b\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\n0\t0\u00032\b\b\u0001\u0010\u000b\u001a\u00020\fH§@¢\u0006\u0002\u0010\rJ\u001e\u0010\u000e\u001a\b\u0012\u0004\u0012\u00020\n0\u00032\b\b\u0001\u0010\u000f\u001a\u00020\fH§@¢\u0006\u0002\u0010\rJ\u001a\u0010\u0010\u001a\u000e\u0012\n\u0012\b\u0012\u0004\u0012\u00020\n0\t0\u0003H§@¢\u0006\u0002\u0010\u0011J\u001e\u0010\u0012\u001a\b\u0012\u0004\u0012\u00020\u00130\u00032\b\b\u0001\u0010\u0005\u001a\u00020\u0014H§@¢\u0006\u0002\u0010\u0015J\u001e\u0010\u0016\u001a\b\u0012\u0004\u0012\u00020\u00130\u00032\b\b\u0001\u0010\u0005\u001a\u00020\u0017H§@¢\u0006\u0002\u0010\u0018J\u001e\u0010\u0019\u001a\b\u0012\u0004\u0012\u00020\u00130\u00032\b\b\u0001\u0010\u0005\u001a\u00020\u001aH§@¢\u0006\u0002\u0010\u001b¨\u0006\u001c"}, d2 = {"Lcom/factory/wms/data/api/WmsApiService;", "", "login", "Lcom/factory/wms/data/model/ApiEnvelope;", "Lcom/factory/wms/data/model/LoginData;", "request", "Lcom/factory/wms/data/model/LoginRequest;", "(Lcom/factory/wms/data/model/LoginRequest;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "searchMaterial", "", "Lcom/factory/wms/data/model/MaterialDto;", "keyword", "", "(Ljava/lang/String;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "materialInfo", "code", "allMaterials", "(Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "submitInbound", "Lcom/factory/wms/data/model/SubmitResult;", "Lcom/factory/wms/data/model/InboundRequest;", "(Lcom/factory/wms/data/model/InboundRequest;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "submitOutbound", "Lcom/factory/wms/data/model/OutboundRequest;", "(Lcom/factory/wms/data/model/OutboundRequest;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "submitStocktake", "Lcom/factory/wms/data/model/StocktakeRequest;", "(Lcom/factory/wms/data/model/StocktakeRequest;Lkotlin/coroutines/Continuation;)Ljava/lang/Object;", "app_debug"}, k = 1, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes9.dex */
public interface WmsApiService {
    @GET("api/material/all")
    Object allMaterials(Continuation<? super ApiEnvelope<List<MaterialDto>>> continuation);

    @POST("api/login")
    Object login(@Body LoginRequest loginRequest, Continuation<? super ApiEnvelope<LoginData>> continuation);

    @GET("api/material/info")
    Object materialInfo(@Query("code") String str, Continuation<? super ApiEnvelope<MaterialDto>> continuation);

    @GET("api/material/search")
    Object searchMaterial(@Query("keyword") String str, Continuation<? super ApiEnvelope<List<MaterialDto>>> continuation);

    @POST("api/inbound")
    Object submitInbound(@Body InboundRequest inboundRequest, Continuation<? super ApiEnvelope<SubmitResult>> continuation);

    @POST("api/outbound")
    Object submitOutbound(@Body OutboundRequest outboundRequest, Continuation<? super ApiEnvelope<SubmitResult>> continuation);

    @POST("api/stocktake")
    Object submitStocktake(@Body StocktakeRequest stocktakeRequest, Continuation<? super ApiEnvelope<SubmitResult>> continuation);
}
