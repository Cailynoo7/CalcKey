"""Create or verify a blank assembly record; never contact hardware or overwrite observations."""
import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "unpowered-checklist.csv"
AUDIT_PATH = HERE / "source-checks.json"
FIELDS = ["编号", "阶段", "项目", "红表笔", "黑表笔", "档位或方法", "前置条件", "判据",
          "来源", "实测或观察", "结果", "异常与处理", "复查结果", "操作者", "日期"]
USER_FIELDS = ["实测或观察", "异常与处理", "复查结果", "操作者", "日期"]
LABELS = ["Num", "÷", "×", "Bk", "7", "8", "9", "−", "4", "5", "6", "+",
          "1", "2", "3", "Enter/=", "Mode", "0", ".", "AC"]
MATRIX_PINS = [("ROW0", "GP2", 4), ("ROW1", "GP3", 5), ("ROW2", "GP4", 6),
               ("ROW3", "GP5", 7), ("ROW4", "GP6", 9), ("COL0", "GP7", 10),
               ("COL1", "GP8", 11), ("COL2", "GP9", 12), ("COL3", "GP10", 14),
               ("V3V3", "3V3 OUT", 36)]
LCD_PINS = [("/CS", "GP11", 15), ("/WR", "GP1", 2), ("DATA", "GP0", 1),
            ("VSS", "GND", 38), ("VDD", "3V3 OUT", 36)]
PCB_GUIDE = "product/matrix-assembly-diagrams/guided-soldering.md"
HARNESS = "product/harness-routing.md"
CASE_GUIDE = "design/enclosure/README.md"


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def read_csv(path):
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def prepare():
    binding = read_json("product/production/harness-delivery-addendum.json")
    cad = binding["cad_export"]
    receipt = read_json(cad["receipt"])
    assert cad["revision"] == receipt["revision"]
    assert cad["export_id"] == receipt["exportId"]
    assert cad["step_sha256"] == receipt["artifacts"][0]["sha256"]
    assert sha(receipt["artifacts"][0]["path"]) == cad["step_sha256"]
    assert receipt["revision"] == "fbc7b5b086d7cbc1a9d57411878b97d43cc429c3d95ad141d3f641841fb9ded7"
    constraints = read_json("product/constraints.json")
    h = constraints["harness_retention"]
    assert h["integral_bridge_count"] == 5
    assert h["slot_size_mm"] == [10.6, 2]
    assert h["matrix_free_span_min_mm"] == 65 and h["wire_total_length_default_mm"] == 150
    assert h["bottom_service_opening_mm"] == 30 and h["lcd_fixed_only_to_base"]
    assert h["top_bridge_root_centres_mm"] == [[-17, -55.7, 5.2], [17, -55.7, 5.2]]
    assert h["base_bridge_root_centres_mm"] == [[0, -29, 2.4], [0, 23, 2.4], [-26, 2, 2.4]]
    assert constraints["wiring_storage"]["zones"] == [
        {"id": "matrix_left", "center_mm": [-26, -36.7, 4.55], "size_mm": [20, 21.4, 3]},
        {"id": "matrix_right", "center_mm": [26, -36.7, 4.55], "size_mm": [20, 21.4, 3]},
        {"id": "lcd_spare", "center_mm": [-26, -15.5, 4.55], "size_mm": [20, 18, 3]}]
    pins = read_csv("product/matrix-assembly-diagrams/soldering-map.csv")
    assert len(pins) == 19
    for i, expected in enumerate(MATRIX_PINS):
        row = pins[i]
        assert row["焊点"] == f"J{i+1}"
        assert (row["信号"], row["Pico信号"], int(row["Pico物理脚号"])) == expected
    for i, expected in enumerate(LCD_PINS):
        row = pins[10+i]
        assert row["焊点"] == f"P{i+1}"
        assert (row["信号"], row["Pico信号"], int(row["Pico物理脚号"])) == expected
    assert all(r["Pico信号"] == "NC" and not r["Pico物理脚号"] for r in pins[15:])
    legacy = read_csv("product/matrix-assembly-diagrams/unpowered-check-record.csv")
    assert len(legacy) == 59
    assert all(not r["实测"] and r["结果"] == "待测" for r in legacy)
    for i, row in enumerate(legacy[:4]):
        assert (row["红表笔"], row["黑表笔"]) == (f"J{i+6}", "J10")
    for i in range(20):
        forward, reverse = legacy[4+2*i:6+2*i]
        row_pad, col_pad = f"J{i//4+1}", f"J{i%4+6}"
        assert forward["项目"] == reverse["项目"] == f"SW{i+1}/D{i+1}"
        assert (forward["红表笔"], forward["黑表笔"]) == (col_pad, row_pad)
        assert (reverse["红表笔"], reverse["黑表笔"]) == (row_pad, col_pad)
    for row, pin in zip(legacy[44:], pins[:15]):
        expected_from = pin["焊点"] if pin["部件"] == "矩阵PCB" else "LCD " + pin["焊点"]
        assert row["红表笔"] == expected_from
        assert row["黑表笔"] == "Pico物理" + pin["Pico物理脚号"]
    return binding, cad, legacy


def make_rows(legacy, cad):
    rows = []

    def add(id_, stage, item, method, condition, expected, source, red="", black=""):
        row = dict.fromkeys(FIELDS, "")
        row.update(编号=id_, 阶段=stage, 项目=item, 红表笔=red, 黑表笔=black,
                   档位或方法=method, 前置条件=condition, 判据=expected, 来源=source, 结果="待测")
        rows.append(row)

    def group(prefix, stage, entries, source):
        for i, (item, method, condition, expected) in enumerate(entries, 1):
            add(f"{prefix}{i:02d}", stage, item, method, condition, expected, source)

    group("A", "00 版本与准备", [
        ("主壳/底盖版本", "目视并对照导出", "仅核对资料或已有实物，不启动打印", f"主壳前内壁2桥、底盖3桥；采用{cad['revision'][:8]}/{cad['export_id']}，STEP/STL与完整包按当前清单取用"),
        ("外部电源全部断开", "目视线缆", "任何电阻/通断/二极管测量之前", "USB、充电器、调试器等均断开；若曾供电先测残余电压，不短接电容"),
        ("表笔插孔与表线基准", "电阻档短接/分开表笔", "红V/Ω、黑COM，待测电路无残余电压", "记录表线基准Ω与分开OL，不用电流档"),
        ("28件及机构备件", "点数/目视", "已取得实物时；不在本次打印", "28个打印件、单独保护片、两D12×2前垫、两后脚/短轴/盲帽齐全，孔内无残丝碎屑"),
        ("六颗紧固螺钉", "点数与长度核对", "安装前", "4颗ISO7380-1 M3×8合盖；2颗ISO4762 M2×4固定Pico，旧OLED螺钉不混用"),
        ("LCD与轴体识别", "看型号/版本/P1", "用户已确认KS-9对应关系；到货复核不改变选型", "LCD为GDM0103 3.3V/6点钟，认P1；轴为既定KS-9H10B045NN-X14三脚红轴"),
        ("15根软线及胶带", "点数/量尺寸", "未裁短末端", "10矩阵+5LCD、26AWG柔性线外径≤1.3mm、每根总长默认150mm；胶带10mm宽/总厚≤0.1mm")], CASE_GUIDE + "; " + HARNESS)
    group("B", "10 独立矩阵", [
        ("四只上拉装配", "目视/核型号", "Pico/LCD未接矩阵，所有键松开", "R1～R4为10kΩ±1%/0805、坐平无锡桥；按图核位置"),
        ("二十只二极管方向", "目视/核K", "屏幕端朝上看PCB底面", "20只1N4148-TAP底面卧装，黑环K左侧对方形pad1，无玻璃裂纹，正面剪脚不顶轴"),
        ("20轴与40处触点", "目视/轻按", "键帽未装、Pico/LCD未接", "20轴坐平且PCB不翘，40个金属触点焊好；20个中心塑料柱NPTH孔未焊"),
        ("被动矩阵焊后清理", "放大目视", "焊点冷却", "无散股、锡桥、金属屑或虚焊；不做旧版跨键并线")], PCB_GUIDE)

    def import_legacy(index):
        r = legacy[index]
        stage = "10 独立矩阵" if index < 44 else "20 软线焊装"
        method = "电阻档" if index < 4 else "二极管档" if index < 44 else "电阻/通断档，记录实际读数"
        add(f"E{index+1:02d}", stage, r["项目"], method, r["条件"], r["预期"],
            f"product/matrix-assembly-diagrams/unpowered-check-record.csv：数据行{index+1}",
            r["红表笔"], r["黑表笔"])

    for i in range(4):
        import_legacy(i)
    for i in range(20):
        for index in [4+2*i, 5+2*i]:
            import_legacy(index)
        add(f"R{i+1:02d}", "10 独立矩阵", f"SW{i+1} {LABELS[i]} 松开与释放", "二极管档，记起始松开/测后释放两个读数",
            "Pico/LCD未连接；其他19键松开；正反测后恢复红列黑行再释放", "起始松开OL；测后释放也为OL", PCB_GUIDE,
            f"J{i%4+6}", f"J{i//4+1}")

    group("C", "20 软线焊装", [
        ("15根导线标签与PCB首段", "目视/逐根对照", "Pico焊端前，板已支撑", "J1～J10及LCD P1～P5两端标号一致；J线朝板内低位直焊，无排针"),
        ("LCD未使用端绝缘", "逐端目视", "不增加背光或/INT连线", "P6～P9各自绝缘，不接外部线、不互短；不把内部任意两NC必须OL作判据"),
        ("LCD板背低位引线", "目视/量突出量", "胶粘安装前，玻璃不受压", "焊点与首段线突出≤1.5mm，朝内，边缘托架承托带不被导线占用"),
        ("Pico物理36共享节点", "目视端点/编号", "Pico按官方方向识别物理编号", "J10与LCD P5同到3V3 OUT/36；LCD P4到GND/38；35/37无意外锡桥"),
        ("矩阵行与电源接法", "逐端目视标签", "不拿芯片内阻猜针脚", "矩阵无GND端子；J1～J5不接地；J10不接VBUS、VSYS、3V3_EN或5V")], PCB_GUIDE)
    for i in range(44, 59):
        import_legacy(i)
    group("D", "30 机械安装", [
        ("翻脚、短轴及盲帽", "干装/观察胶接/轻翻", "两壳有支撑；胶材按要求固化", "17.8mm短轴、Ø5×2.4盲帽，入帽约1mm；胶仅轴端，转动面不粘；0/110°两档限位可达"),
        ("Pico两孔固定", "目视/轻拧", "既有线束松放，不靠线悬吊", "Micro-B向右；2颗M2×4与USB端承托定位，无薄板弯曲或器件挤压"),
        ("LCD四处边缘固定", "实物承托带检查/轻压PCB", "先焊线与绝缘、后粘接；不压玻璃", "四片2×4×0.15mm绝缘胶片；边缘无铜/元件/导线干涉，背面凸起不顶托架"),
        ("保护片与胶框", "目视/干合盖", "67.6×19.6×1mm保护片，0.15mm周边胶框", "64×16mm窗口清洁、无溢胶遮挡，LCD玻璃不顶保护片或受周边挤压")], CASE_GUIDE)
    group("F", "40 固定与余量", [
        ("五处穿带孔可用", "穿带/目视", "新版本实物已备，线束不拉紧", "5个10.6×2mm孔通畅，不以拉扯焊线穿带"),
        ("主壳前两桥分组", "核对局部坐标与标签", "键面朝上、屏幕远端作为左右基准", "(-17,-55.7)固定J1～J5；(17,-55.7)固定J6～J10，每组5线，夹持线皮"),
        ("底盖前中汇线桥", "目视并排宽度", "中心(0,-29)，桥顶z6mm", "10线单层、宽≤13mm，含胶带高度≤1.5mm，无圆束堆高"),
        ("LCD底盖后中桥", "沿五线追踪固定点", "中心(0,23)，桥顶z6mm", "P1～P5仅固定到底盖、不绑主壳或矩阵，5线宽≤6.5mm，含胶带高≤1.5mm"),
        ("左侧辅助桥（可选）", "检查可达余线", "中心(-26,2)；余段自然可达才使用", "不强迫绕远或拉紧；不用时可填不适用并写原因"),
        ("矩阵左右折返区", "目视/量堆高", "各5根线，未把自由段粘到底板", "中心(±26,-36.7,4.55)，各20×21.4×3mm；松弛S形、单根内弯半径默认≥5mm"),
        ("LCD余线区", "目视/量堆高", "只收自然可达余线，不硬塞全线", "中心(-26,-15.5,4.55)，20×18×3mm；无圆线团、无托架夹线"),
        ("Pico上方扇出与焊端下降", "侧视/干合盖观察", "42×23×1.5mm中间预算中心(14,-9.5,10.05)", "不压Pico元件/矩阵焊脚/USB；焊端另落真实焊盘，0.505mm模型余隙不当实物保证"),
        ("胶带长度与搭接", "量宽/搭接与松紧", "默认5条10×65mm、总厚≤0.1mm", "穿桥后包住线皮，尾搭≥15mm；不勒凹线皮，不粘住跨壳自由段"),
        ("独立绝缘与带尾", "放大目视", "所有焊点冷却且绝缘完毕", "裸铜/引脚独立绝缘；固定胶带不代替热缩管，不贴玻璃，带尾不入柱/唇/轴脚/翻脚"),
        ("自由段长度定义", "逐根沿线量弧长", "参照S01～S10记录，不以两桥直线距离替代", "150mm为每根总长；不足时延长并记实际长度，不缩减65mm维护段")], HARNESS)
    for i in range(10):
        side = "前左" if i < 5 else "前右"
        add(f"S{i+1:02d}", "40 固定与余量", f"J{i+1} 跨壳自由长度", "沿线量弧长；记自由长度mm、总线长mm及弯曲观察",
            f"主壳{side}桥夹持区至底盖前中桥夹持区；该线未被中途粘死",
            "自由长度≥65mm；总长默认150mm；松弛折返且单根内弯半径默认≥5mm；30mm开盖另在M项实物观察", HARNESS)
    for i, (item, method, condition, expected, red, black) in enumerate([
        ("无外部供电再确认", "目视", "合盖前电气复测", "USB/充电器/调试器全部断开；曾供电先查残余电压", "", ""),
        ("J10与LCD P5共享3V3", "电阻/通断档", "Pico已连接，设备无残余电压", "记录读数，应为同一节点且接近表线基准；到物理36的单线结果另见E项", "J10", "LCD P5"),
        ("合盖前3V3—GND", "电阻档，记录正/反接稳定值及变化趋势", "全程无外部供电，芯片已经接入", "无固定阻值/必须OL要求；持续近表线基准的低阻须查明，不能以一次不蜂鸣通过", "Pico物理36", "Pico物理38"),
        ("相邻焊点和电源区目视", "放大目视，重点物理35～38", "已接芯片，不给所有相邻脚套OL判据", "无锡桥、裸线散股及残留金属；不确定的读数需记录并定位", "", "")], 1):
        add(f"P{i:02d}", "50 合盖前电气", item, method, condition, expected, PCB_GUIDE, red, black)
    for i, label in enumerate(LABELS, 1):
        note = "；5键有浅圆定位凹点" if i == 10 else "；Enter与=为双行" if i == 16 else ""
        add(f"K{i:02d}", "60 逐键回弹", f"SW{i} {label} 三阶段机械检查",
            "分别记轴体/装帽开盖/合盖后三段观察", "全程断电；只按至轴正常止点，不过压凑4mm",
            f"标签与布局一致、坐平、按下和释放不卡壳不蹭邻帽，合盖后仍自然回弹{note}", CASE_GUIDE)
    group("M", "70 合盖与维护", [
        ("自然合缝", "托住两壳轻合/观察四周", "线束已整理，先不依靠螺钉拉合", "定位唇自然贴合，无回弹、顶LCD或PCB弯曲，无柱/唇/USB/轴脚夹线"),
        ("四颗底部螺钉", "核长度/轻拧", "自然合缝后", "仅4颗M3×8向上合盖，不强拧掩盖缝隙；后续可正常拆卸"),
        ("Micro-B机械试插", "使用另一端悬空的线头试插后拔出", "不接电脑、充电器或任何供电端", "插头机械出入不挤壳、不牵线；不做USB枚举或供电测试"),
        ("两档支撑与前垫", "抬起切档后轻放水平面", "两只后脚在同一实体限位档，前D12×2垫齐全", "观察落桌贴合、摇晃、滑移、回折或帽松动；如有异常记录，不把几何核对当承载实测"),
        ("20键合盖后复查", "逐键轻按并释放", "K01～K20均填合盖后观察", "20键均回弹；SW10定位凹点、SW16 Enter/=位置正确，未以合盖压平PCB"),
        ("30mm维护开口", "卸4颗M3、手托底盖沿局部负z缓慢下放并量开口", "外部线缆全断，两壳均受支撑", "可到30mm；10矩阵线自然展开，桥处不滑移、线皮不紧、焊点不受拉；遇阻停止重排"),
        ("LCD随底盖移动", "观察LCD五线与模块", "30mm开口过程中，不撬玻璃", "LCD与Pico一同移动，LCD线没有跨上壳固定；完全分离仍需断开焊线"),
        ("重合盖后供电节点", "同档位记录3V3—GND方向/稳定值/趋势", "外部供电断开，对照P03", "不得出现未解释的新持续近表线低阻；读数变化先查，不要求固定阻值或OL"),
        ("重合盖后机构与残屑", "目视并复查受影响K项", "重新排线或返修后", "无夹线/裸铜/碎屑，键、翻脚与USB口不受干涉；修复有复查记录"),
        ("记录与本阶段结束", "检查未填项、异常及引用记录", "仅在确实操作并提供实测后判断完成", "必测项有记录，异常有处置/复查；缺项不代填通过；停在断电检查，功能待后续验收")], HARNESS + "; " + PCB_GUIDE)
    assert len({r["编号"] for r in rows}) == len(rows)
    assert len([r for r in rows if r["编号"].startswith("E")]) == 59
    assert len([r for r in rows if r["编号"].startswith("R")]) == 20
    assert len([r for r in rows if r["编号"].startswith("K")]) == 20
    assert len([r for r in rows if r["编号"].startswith("S")]) == 10
    assert all(not r[f] for r in rows for f in USER_FIELDS)
    assert all(r["结果"] == "待测" for r in rows)
    return rows


def serialized_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")


def protect_observations():
    if not CSV_PATH.exists():
        return
    old = read_csv(CSV_PATH.relative_to(ROOT))
    if any(r.get("结果") != "待测" or any(r.get(f) for f in USER_FIELDS) for r in old):
        raise SystemExit("已有实测或结果修改，拒绝覆盖；请保留该记录，为新版本另建记录。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    binding, cad, legacy = prepare()
    rows = make_rows(legacy, cad)
    payload = serialized_csv(rows)
    inputs = ["product/final-assembly/generate.py", "README.md", "product/production/README.md",
              "product/matrix-assembly-diagrams/README.md", "product/matrix-assembly-diagrams/unpowered-check-record.csv",
              "product/matrix-assembly-diagrams/soldering-map.csv", PCB_GUIDE, HARNESS, CASE_GUIDE,
              "product/constraints.json", "product/bom.json", "design/enclosure/source/wiring.json",
              "product/harness-routing-verification.json", "product/production/harness-delivery-addendum.json",
              "manufacturing/matrix/release-index.json", cad["receipt"],
              f"manufacturing/matrix/releases/{binding['pcb_release_id']}/release-manifest.json"]
    audit = {"kind": "assembly_document_consistency", "prepared_date": "2026-11-06",
             "cad_revision": cad["revision"], "cad_export_id": cad["export_id"],
             "pcb_release_id": binding["pcb_release_id"], "firmware_version": binding["firmware_version"],
             "row_count": len(rows), "rows_by_phase": dict(Counter(r["阶段"] for r in rows)),
             "retained_electrical_rows": 59, "added_release_rows": 20, "per_key_mechanical_rows": 20,
             "per_wire_free_length_rows": 10, "all_observation_fields_blank": True,
             "all_results": "待测", "physical_checks_executed": 0,
             "scope": "Document preparation only; no printing, external power, flashing or physical assembly.",
             "input_hashes": {p: sha(p) for p in inputs},
             "document_hashes": {"product/final-assembly/README.md": sha("product/final-assembly/README.md"),
                                  "product/final-assembly/unpowered-checklist.csv": hashlib.sha256(payload).hexdigest()},
             "checks": ["Current STEP hash matches its domain export receipt",
                        "Five bridges, three storage zones, 150mm total/65mm free/30mm opening match constraints",
                        "All 59 original electrical rows retained with identical probes, conditions and criteria",
                        "15 wire endpoints match the existing soldering map; four LCD NC endpoints unconnected",
                        "20 release rows, 20 mechanical key rows and 10 free-length rows have unique identifiers",
                        "All physical result fields remain blank/pending"],
             "limitations": ["Documentation checks are not physical measurements or functional acceptance.",
                             "Use the current mesh/package manifests; historical exports do not identify the current delivery.",
                             "Independent-matrix criteria are not applied to a matrix already connected to Pico/LCD."]}
    if args.check_only:
        assert CSV_PATH.read_bytes() == payload, "清单与当前空白模板或输入不一致"
        assert read_json(AUDIT_PATH.relative_to(ROOT)) == audit, "来源记录与当前文件不一致"
    else:
        protect_observations()
        CSV_PATH.write_bytes(payload)
        AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS {len(rows)} pending assembly checks: 59 retained electrical, 20 release, 20 mechanical key, "
          "10 free-length plus whole-device checks; current source hashes and 15 wire endpoints verified.")


if __name__ == "__main__":
    main()
