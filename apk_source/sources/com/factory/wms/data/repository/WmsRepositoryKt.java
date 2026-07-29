package com.factory.wms.data.repository;

import com.factory.wms.data.local.CachedMaterialEntity;
import com.factory.wms.data.model.MaterialDto;
import kotlin.Metadata;

/* compiled from: WmsRepository.kt */
@Metadata(d1 = {"\u0000\u000e\n\u0000\n\u0002\u0018\u0002\n\u0002\u0018\u0002\n\u0002\b\u0002\u001a\f\u0010\u0000\u001a\u00020\u0001*\u00020\u0002H\u0002\u001a\f\u0010\u0003\u001a\u00020\u0002*\u00020\u0001H\u0002¨\u0006\u0004"}, d2 = {"toEntity", "Lcom/factory/wms/data/local/CachedMaterialEntity;", "Lcom/factory/wms/data/model/MaterialDto;", "toDto", "app_debug"}, k = 2, mv = {2, 0, 0}, xi = 48)
/* loaded from: classes6.dex */
public final class WmsRepositoryKt {
    /* JADX INFO: Access modifiers changed from: private */
    public static final CachedMaterialEntity toEntity(MaterialDto $this$toEntity) {
        String code = $this$toEntity.getCode();
        String name = $this$toEntity.getName();
        String spec = $this$toEntity.getSpec();
        String unit = $this$toEntity.getUnit();
        double stock = $this$toEntity.getStock();
        String warehouseCode = $this$toEntity.getWarehouseCode();
        if (warehouseCode == null) {
            warehouseCode = $this$toEntity.getLocationCode();
        }
        return new CachedMaterialEntity(code, name, spec, unit, stock, warehouseCode, System.currentTimeMillis());
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static final MaterialDto toDto(CachedMaterialEntity $this$toDto) {
        return new MaterialDto(null, $this$toDto.getCode(), $this$toDto.getName(), $this$toDto.getSpec(), $this$toDto.getUnit(), $this$toDto.getStock(), $this$toDto.getWarehouseCode(), null, 129, null);
    }
}
