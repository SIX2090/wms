package com.factory.wms.update

/** One process-wide lock: acquiring installation and starting a write are atomic. */
internal class UpdateBusinessGate {
    private var writers = 0
    private var installing = false

    @Synchronized fun enterBusiness(): Boolean {
        if (installing) return false
        writers++
        return true
    }

    @Synchronized fun leaveBusiness() {
        check(writers > 0)
        writers--
    }

    @Synchronized fun beginInstall(): Boolean {
        if (installing || writers != 0) return false
        installing = true
        return true
    }

    @Synchronized fun endInstall() { installing = false }

}

internal val businessUpdateGate = UpdateBusinessGate()
