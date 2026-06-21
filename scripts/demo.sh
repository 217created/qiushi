#!/usr/bin/env bash
# 快速演示脚本
set -e

echo "=== 求是 (QiuShi) 演示 ==="
echo ""

echo "1. 快速判断"
qiushi ask "该不该辞职" --depth 1
echo ""

echo "2. 标准深度分析"
qiushi ask "最近压力很大" --depth 2
echo ""

echo "3. 解释模式（展示内部过程）"
qiushi ask "30岁转行来得及吗" --explain
echo ""

echo "4. 多智能体辩论"
qiushi ask "努力重要还是选择重要" --council 3
echo ""

echo "5. 思辨卡片"
qiushi card "自由"
echo ""

echo "6. 文件输入输出"
echo "如何应对职场内卷？" > /tmp/qiushi_question.txt
qiushi ask -i /tmp/qiushi_question.txt -o /tmp/qiushi_answer.txt
cat /tmp/qiushi_answer.txt
echo ""

echo "=== 演示结束 ==="
