package com.factory.wms.ui.viewmodel;

import com.factory.wms.data.model.MaterialDto;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import kotlin.Metadata;
import kotlin.collections.CollectionsKt;
import kotlin.jvm.internal.Intrinsics;
import okhttp3.internal.ws.WebSocketProtocol;

/* compiled from: MainViewModel.kt */
@Metadata(d1 = {"\u0000\u0014\n\u0000\n\u0002\u0010 \n\u0002\u0018\u0002\n\u0000\n\u0002\u0018\u0002\n\u0002\b\u0002\u001a \u0010\u0000\u001a\b\u0012\u0004\u0012\u00020\u00020\u0001*\b\u0012\u0004\u0012\u00020\u00020\u00012\u0006\u0010\u0003\u001a\u00020\u0004H\u0002\u001a \u0010\u0005\u001a\b\u0012\u0004\u0012\u00020\u00020\u0001*\b\u0012\u0004\u0012\u00020\u00020\u00012\u0006\u0010\u0003\u001a\u00020\u0004H\u0002¨\u0006\u0006"}, d2 = {"bumpOrAdd", "", "Lcom/factory/wms/ui/viewmodel/ScanLine;", "material", "Lcom/factory/wms/data/model/MaterialDto;", "bumpOrAddActual", "app_debug"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes10.dex */
public final class MainViewModelKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final List<ScanLine> bumpOrAdd(List<ScanLine> list, MaterialDto material) {
        ScanLine scanLine;
        boolean found = false;
        List<ScanLine> $this$map$iv = list;
        Collection destination$iv$iv = new ArrayList(CollectionsKt.collectionSizeOrDefault($this$map$iv, 10));
        for (Object item$iv$iv : $this$map$iv) {
            ScanLine it = (ScanLine) item$iv$iv;
            if (Intrinsics.areEqual(it.getMaterial().getCode(), material.getCode())) {
                found = true;
                scanLine = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : 1 + it.getQuantity(), (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : 0.0d, (r20 & 64) != 0 ? it.scannedTimes : it.getScannedTimes() + 1);
            } else {
                scanLine = it;
            }
            destination$iv$iv.add(scanLine);
        }
        List updated = (List) destination$iv$iv;
        return found ? updated : CollectionsKt.plus((Collection<? extends ScanLine>) updated, new ScanLine(material, 0.0d, null, null, null, 0.0d, 0, WebSocketProtocol.PAYLOAD_SHORT, null));
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final List<ScanLine> bumpOrAddActual(List<ScanLine> list, MaterialDto material) {
        ScanLine scanLine;
        boolean found = false;
        List<ScanLine> $this$map$iv = list;
        Collection destination$iv$iv = new ArrayList(CollectionsKt.collectionSizeOrDefault($this$map$iv, 10));
        for (Object item$iv$iv : $this$map$iv) {
            ScanLine it = (ScanLine) item$iv$iv;
            if (Intrinsics.areEqual(it.getMaterial().getCode(), material.getCode())) {
                found = true;
                scanLine = it.copy((r20 & 1) != 0 ? it.material : null, (r20 & 2) != 0 ? it.quantity : 0.0d, (r20 & 4) != 0 ? it.batchNo : null, (r20 & 8) != 0 ? it.receiver : null, (r20 & 16) != 0 ? it.department : null, (r20 & 32) != 0 ? it.actualStock : it.getActualStock() + 1, (r20 & 64) != 0 ? it.scannedTimes : it.getScannedTimes() + 1);
            } else {
                scanLine = it;
            }
            destination$iv$iv.add(scanLine);
        }
        List updated = (List) destination$iv$iv;
        return found ? updated : CollectionsKt.plus((Collection<? extends ScanLine>) updated, new ScanLine(material, 0.0d, null, null, null, 1.0d, 0, 94, null));
    }
}
