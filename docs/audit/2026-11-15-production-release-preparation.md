# 生产发布候选准备记录（2026-11-15）

状态：发布候选准备和隔离验证完成，未部署，未验证生产启动。

任务 RELEASE-PREP-20261115-001，关联既有七组后端/Web交付及AI-APP-AUDIT-FIX-20261115-001。用户已授权发布准备，并再次明确禁止触碰生产数据库。

## 操作边界与当前状态

生产数据库、WAL/SHM、备份、凭据均未连接、查询、复制、迁移、校验；未向现役服务发HTTP，未停止/重启、部署或安装APK。读取仅限明确允许的程序源码/程序清单与进程、端口元数据。程序制品准备与真实生产生效分别登记。

现役8080 PID8896，旧完整制品位于C:/wms_releases/20261113_toastfix_afe8c9ad，backend3652607ac6f381dd39e05e183c276dba443f508a、UIafe8c9ad89d0d9bc408482ba88846a9b9133b307，artifact36d24a2bb6f7d4c6aa15a2e6f94beb513c714984c52fc6a6f07e54b623880722。本轮不操作现役程序入口。旧launch/preflight即使受保护也可能读取现库，本阶段禁止执行。

## 冻结候选

- Git来源f161cbd3c7f15326eedad3d612ea3a7a91e7d6f7；直接导出2775个提交blob，不使用C:/wms工作区，16条原有未提交状态保留。未提交视觉四文件未纳入。
- 运行时来自官方windows-v2026.11.76，源dbe403058eec536ab93411906bc0b44de023b871。97,382,974字节公开ZIP已核SHA256=17ee8e9cdfa225c070a652ebe47fe6442f6521c1622d1b6a627ec361f357ce2a；官方8项runtime检查成功。dbe到f161的Windows实际build_inputs指纹均d965667d32d9b4ef0382adc2c23ddeedb01dfca2c3ff106e7a1ab5dcc9dbc539。只复制6758个清单内不可变runtime文件，不带可再生pyc。
- Python3.11.9、34项精确依赖与现役纯程序清单比较，无缺项/多项/版本差异；模型/schema/启动迁移源码没有新需求，35个变化Python文件未新增DDL。此为源码/制品兼容性检查，不是现库结构审计。
- APK54/3.9.30来自android-apk-896-attempt-1，25,594,179字节，SHA256=d1439798c6385c5e78a2a2bb7d9d0c42a4d743dcf7d9bf8a6e720fc0b0e49cfd，只下载校验，未安装。
- 候选7430个不可变文件，source/UI均f161，artifact_id=1f7b13bebd38246103d21504e8a861102bd8ef560b0c565e3ff52c421f3b2ee1。保留原受保护启动链，controlled_server仅替换固定current SHA常量，恢复该常量后的AST与原始完全相等；SKIP、启动写保护、网络限制、凭据处理和任务逻辑不改。

## 43文件覆盖层三方核对

32份与旧Git及目标同源；3份旧Git同源但目标已更新；另8份生产偏离旧Git，其中7份旧金额/显式0/盘点confirmation_token等回退不得覆盖新修复，唯一保留的独有内容是material.html候选图片警示文案一行。只保留4文件兼容覆盖：material.html目标版+一行文案，以及原loader固定映射的3份目标静态文件。其余42份均使用目标，不直接搬旧43覆盖。完整raw/LF hash、差异及覆盖清单在仓库外三方记录。

## 代码回退与封装

仅在新私有CAS目录，从实际active-code指针逐文件读取：候选7430→旧7525→恢复候选7430，size/hash/manifest集合全部相等。恢复前后listing SHA均a0eeca48b7f5c83ae99ea61bb60c0e099b2bda29c00ce389ee19515e66c3f38a。不运行启动、不做数据回退，也不能将其称为生产进程回退实测；实际回退应选择保留的完整旧制品，而非候选的旧rollback参数。

候选ZIP：WMS-2026.11.76-f161cbd3-candidate.zip，82,967,607字节，7431项（包含自身wms-release清单），逐entry内容已核，SHA256=3ba2711676ac9e9aba7c598bab181b29ddbc21efd9d101788d01a3eb3ea3b5aa。该包是明确记录的组合制品，不冒充原公开ZIP。

## 已完成的隔离验证

- 新建LPAC环境先真实证明隔离：主/子AppContainer token、NO_ALL_APPPKG、源码/runtime只读ACL、外部自有canary拒绝、两类自建SQLite正例、IPv4/IPv6高位网络拒绝均通过。未尝试生产访问。
- 七域13个模块544 passed，0失败/错误/跳过，166条既有warning；直接核对JUnit的544个testcase。此证据只计一次，后续应用与浏览器接线使用9534个相同程序组件的摘要证明复用，未累加次数。组件SHA256=c9277a0cb45284c412340bf378a5b280cfdda4e67e1a18f66f4cea349bff2180。
- 真实私有Python3.11.9与34项依赖检查成功。真实Flask安装原覆盖loader；3份目标静态文件、money.js回落、9个模板来源、物料警示、匿名拒绝、404、篡改/未列文件拒绝均通过。
- 真实Chrome在7个可见业务Frame完成10项检查，291个真实Flask GET；包括显式零价、1.15×3.5=4.03、半分0.01、采购申请零预估价、销售新增/编辑零税，以及盘点confirmation_token阻断与传递。pageErrors、业务网络写入及外域请求均0；所有数据为新建合成数据，未实际保存业务单据。
- 应用始终在LPAC内全出站拒绝；Chrome经host自有随机高位GET broker和只读文件IPC获取真实Flask test_client响应。没有在host导入应用或打开数据库，不将其称为生产TCP或完整受保护启动验收。
- 最终LPAC Job归零、两条本轮SID专属WFP删除并反查不存在、profile删除、受保护文件摘要不变；Node/Chrome独占Job归零，broker清理无错误。没有按进程名终止其他任务或现役程序。
- 前置目录、日志路径、缺失Android夹具及隐藏body定位等接线失败均保留原始结果；只修外置夹具，不改产品/候选/业务断言，不把夹具失败当成旧产品失败。最终完整可见UI检查重新执行通过。

仓库外证据根：C:/Users/Administrator/.codex/visualizations/2026/11/15/01a1de80-0f3b-75d1-bcbd-a7f2c7e704aa/release-preparation-20261115。
核心证据为release-compatibility-verification.json、modules-544-passed.xml、fresh-lpac-application-result.json、fresh-browser-owned-job-result.json、candidate-archive-proof.json、code-rollback-rehearsal-latest.json。截图output/playwright/overlay-KXos89/sales-edit-money-zero-tax.png已人工查看，数量1.15、单价3.5、税率0、金额4.03、税额0.00真实可见。

既有代码验收：dbe403058eec536ab93411906bc0b44de023b871的[WMS CI](https://github.com/SIX2090/wms/actions/runs/43718443314)、[WMS AI Verification](https://github.com/SIX2090/wms/actions/runs/43718443243)、[Android APK Build](https://github.com/SIX2090/wms/actions/runs/43718443363)均success；来源文档目标f161的[WMS CI](https://github.com/SIX2090/wms/actions/runs/43719970569)、[AI](https://github.com/SIX2090/wms/actions/runs/43719970587)均success，Android按完整祖先与路径不变证明复用上述896。本轮仅新增发布准备文档，自身精确提交CI独立核验，不改变候选来源f161或制品身份。

## 仍不执行的事项

生产数据库兼容性/真实启动/切换/重启/公网业务/现场打印/微信/模型/手机安装均未验。生产正在使用，维持原状。任何会读取现库的启动步骤都停在执行前，不从本次准备授权推导数据库例外。

特别说明：候选包不含数据库、私有数据或指向生产数据的目录联接；未建立persistent_paths的真实生产映射，因此不能把封存ZIP当作已安装/已切换的制品。旧launch.cmd/--preflight会进入现有数据启动链，本阶段均不执行。
