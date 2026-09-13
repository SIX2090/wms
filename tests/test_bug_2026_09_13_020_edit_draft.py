from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / 'app/android-native-wms/app/src/main/java/com/factory/wms'


def test_edit_draft_scoped_storage():
    source = (ROOT / 'data/repository/WmsRepository.kt').read_text(encoding='utf-8')
    assert 'suspend fun editDraftKey(' in source
    assert 'preferences[KEY_BASE_URL]' in source
    assert 'preferences[KEY_USERNAME]' in source
    assert 'suspend fun saveEditDraft(' in source
    assert 'it.remove(stringPreferencesKey(key))' in source


def test_edit_draft_restore_before_loading_warehouses():
    source = (ROOT / 'ui/screens/ScanScreens.kt').read_text(encoding='utf-8')
    for operation in ['inbound', 'outbound']:
        assert f'viewModel.restoreEditDraft("{operation}")' in source


def test_edit_draft_persist_before_submit_and_reuse_key():
    source = (ROOT / 'ui/viewmodel/scan/ScanViewModel.kt').read_text(encoding='utf-8')
    assert 'draftMutex.withLock' in source
    assert '已恢复上次未提交清单' in source
    assert 'pendingSubmissionId = draft.requestId' in source
    for method in ['submitInbound', 'submitOutbound']:
        body = source.split(f'fun {method}(', 1)[1].split('\n    fun ', 1)[0]
        assert body.index('prepareDraftSubmission()') < body.index(f'repository.{method}(')
        assert 'finishDraftSubmission(result)' in body
