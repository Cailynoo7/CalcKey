> 历史资料：手焊行列版九页焊接手册，不是当前MATRIX A矩阵PCB的操作依据。当前请用product/matrix-assembly-diagrams中的四页焊装图、guided-soldering操作手册与59项待测记录；不要按本目录重新并行列或采购轴向上拉电阻。

# CalcKey GDM0103断电焊接操作包（LCD-B / 固件v0.2.0）

提供9页A4打印指南、同内容Markdown和5张可填写CSV记录表。CSV以UTF-8 BOM编码，所有实物状态均为“待测”。配合4页A3接线图；操作包中附有该PDF、四张SVG、逐键表及9端子LCD对照表。

顺序：断电与散件检查 → 单键试焊 → 行列总线 → 20键隔离测量 → 四个上拉 → LCD端子识别/五线直焊/四端绝缘 → Pico最后接入 → 绝缘与合盖断电复查。

先做独立矩阵三态测试，再接主控。装上拉后，独立矩阵列间约20kΩ正常；接主控/LCD后不再强求该阻值或任意网络OL。二极管用二极管档确认，蜂鸣不代替正反向测试。详细表笔位置、条件和返工定位见指南。

本操作包不改接线、器件、固件或外壳，也未完成任何实物焊接、绝缘或测量；不执行烧录或通电。依赖安装位置不固定时，设置PYTHONPATH指向含reportlab的环境，再运行generate_soldering_guide.py；版本reportlab==4.4.3，字体可用CALCKEY_DIAGRAM_FONT指定中文TrueType。

## 依据

- Pico 2物理针脚：官方数据表PDF第5页图2：https://pip.raspberrypi.com/documents/RP-008299-DS
- GDM0103厂商手册PDF第7/8页：端子及方向：https://www.radiomag.com.de/datasheets/gdm0103_specification.pdf
- Vishay 1N4148黑环K：PDF第1页：https://www.vishay.com/docs/81857/1n4148.pdf
- Fluke：断电与二极管正反向测量/在路影响：https://www.fluke.com/en-gb/learn/blog/digital-multimeters/how-to-test-diodes
- Kester FAQ：工艺温度取决于焊接材料：https://www.kester.com/knowledge-base/faq
