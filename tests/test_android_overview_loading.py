"""首页／每日报表首次加载的源码接线锁；真实协程行为另由 Android JUnit 验证。"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms'


def _body(source, marker):
    start = source.index('{', source.index(marker))
    depth = 0
    for end in range(start, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError('unclosed Kotlin body: ' + marker)


def _read(relative):
    source = (MAIN / relative).read_text(encoding='utf-8')
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)


class OverviewLoadingContract(unittest.TestCase):
    def test_home_has_one_entry_trigger_and_no_constructor_request(self):
        screen = _read('ui/screens/HomeScreen.kt')
        entry = _body(screen, 'LaunchedEffect(Unit)')
        self.assertEqual(entry.count('homeViewModel.loadDashboard()'), 1)
        self.assertNotIn('loadWarehouses()', entry)
        vm = _read('ui/viewmodel/home/HomeViewModel.kt')
        self.assertNotRegex(vm, r'init\s*\{[^}]*loadDashboard\(')

    def test_daily_report_has_one_entry_trigger(self):
        entry = _body(_read('ui/screens/ReportScreens.kt'), 'LaunchedEffect(Unit)')
        self.assertEqual(entry.count('viewModel.load()'), 1)
        self.assertNotIn('loadWarehouses()', entry)



if __name__ == '__main__':
    unittest.main()
