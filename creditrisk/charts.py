import numpy as np
import pandas as pd
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from sklearn.metrics import confusion_matrix, roc_curve

from .analytics import summary, evaluation, labelled
from .validation import TARGET

COLORS = ["#087f83", "#b77900", "#bd252d"]


class DashboardCharts(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("chartPanel")
        self.frame = pd.DataFrame()
        layout = QVBoxLayout(self)
        self.caption = QLabel("Tải CSV để xem dữ liệu và kết quả dự báo.")
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)
        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Rủi ro dự báo", "Khám phá dữ liệu", "Đánh giá với nhãn thực tế"])
        self.mode.currentIndexChanged.connect(self.redraw)
        controls.addWidget(self.mode)
        controls.addStretch()
        layout.addLayout(controls)
        self.figure = Figure(figsize=(10, 5.6), layout="constrained", facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.canvas.setMinimumHeight(350)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        self.redraw()

    def set_data(self, frame, context=""):
        self.frame = frame.copy()
        stats = summary(frame)
        pd_text = f"{stats['mean_pd']:.2%}" if stats["mean_pd"] is not None else "chưa dự báo"
        actual = (
            f"{stats['actual_default_rate']:.2%}"
            if stats["actual_default_rate"] is not None
            else "không có nhãn"
        )
        self.caption.setText(
            f"{context}\n{stats['rows']:,} hồ sơ · PD trung bình {pd_text} · "
            f"Cảnh báo {stats['warnings']:,} · Rủi ro cao {stats['high_risk']:,} · "
            f"Vỡ nợ thực tế {actual} ({stats['labelled']:,} nhãn hợp lệ)"
        )
        self.redraw()

    def redraw(self, *_):
        self.figure.clear()
        axes = self.figure.subplots(2, 2).ravel()
        d = self.frame
        if d.empty:
            for ax in axes:
                ax.text(
                    0.5,
                    0.5,
                    "Chưa có dữ liệu trong phạm vi đã chọn",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_axis_off()
        elif self.mode.currentIndex() == 1:
            axes[0].hist(d.AGE, bins=15, color="#2460e8", edgecolor="white")
            axes[0].set(title="Phân bố tuổi", xlabel="Tuổi", ylabel="Số hồ sơ")
            axes[1].hist(d.LIMIT_BAL, bins=20, color="#087f83", edgecolor="white")
            axes[1].set(title="Phân bố hạn mức", xlabel="TWD", ylabel="Số hồ sơ")
            education = d.EDUCATION.value_counts().sort_index()
            axes[2].bar(education.index.astype(int).astype(str), education.values, color="#2460e8")
            axes[2].set(title="Trình độ học vấn (mã đã chuẩn hóa)", ylabel="Số hồ sơ")
            delay = d.PAY_0.value_counts().sort_index()
            axes[3].bar(delay.index.astype(int).astype(str), delay.values, color="#087f83")
            axes[3].set(title="Trạng thái trả nợ tháng gần nhất", xlabel="PAY_0", ylabel="Số hồ sơ")
        elif self.mode.currentIndex() == 2:
            known = labelled(d)
            if known.empty or "default_label" not in known:
                for ax in axes:
                    ax.text(
                        0.5,
                        0.5,
                        "Cần nhãn thực tế 0/1 và kết quả dự báo",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                    )
                    ax.set_axis_off()
            else:
                cm = confusion_matrix(known[TARGET], known.default_label, labels=[0, 1])
                axes[0].imshow(cm, cmap="Blues")
                for i in range(2):
                    for j in range(2):
                        axes[0].text(
                            j,
                            i,
                            str(cm[i, j]),
                            ha="center",
                            va="center",
                            color="white" if cm[i, j] > cm.max() / 2 else "#182338",
                        )
                axes[0].set(
                    title="Ma trận nhầm lẫn trên file đã tải",
                    xlabel="Nhãn dự báo",
                    ylabel="Nhãn thực tế",
                    xticks=[0, 1],
                    yticks=[0, 1],
                )
                if known[TARGET].nunique() == 2:
                    fpr, tpr, _ = roc_curve(known[TARGET], known.raw_score)
                    axes[1].plot(fpr, tpr, color="#2460e8")
                    axes[1].plot([0, 1], [0, 1], linestyle="--", color="#64748b")
                axes[1].set(title="ROC · điểm thô", xlabel="False positive rate", ylabel="True positive rate")
                metrics = evaluation(d)
                keys = ["Accuracy", "Precision", "Recall", "F1"]
                axes[2].bar(keys, [metrics[k] for k in keys], color="#087f83")
                axes[2].set(title="Chỉ số trên nhãn hợp lệ của file", ylim=(0, 1))
                counts = known[TARGET].value_counts().reindex([0, 1], fill_value=0)
                axes[3].bar(["Không vỡ nợ", "Vỡ nợ"], counts.values, color=["#087f83", "#bd252d"])
                axes[3].set(title="Nhãn thực tế (không phải nhãn dự báo)", ylabel="Số hồ sơ")
        else:
            if "probability" not in d:
                for ax in axes:
                    ax.text(
                        0.5,
                        0.5,
                        "Chạy dự báo để xem biểu đồ rủi ro",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                    )
                    ax.set_axis_off()
            else:
                counts = d.risk_level.value_counts().reindex(["Low", "Medium", "High"], fill_value=0)
                bars = axes[0].bar(["Thấp", "Trung bình", "Cao"], counts.values, color=COLORS)
                axes[0].bar_label(bars, padding=3, fontsize=8)
                axes[0].set(title="Phân nhóm rủi ro từ PD", ylabel="Số hồ sơ")
                axes[1].hist(
                    d.probability * 100, bins=np.linspace(0, 100, 21), color="#2460e8", edgecolor="white"
                )
                axes[1].set(title="Phân bố PD đã hiệu chỉnh", xlabel="Xác suất (%)", ylabel="Số hồ sơ")
                groups = pd.cut(
                    d.AGE, [17, 29, 39, 49, 59, 100], labels=["18–29", "30–39", "40–49", "50–59", "60+"]
                )
                means = d.groupby(groups, observed=False).probability.mean() * 100
                axes[2].bar(means.index.astype(str), means.fillna(0).values, color="#087f83")
                axes[2].set(title="PD trung bình theo tuổi", ylabel="PD (%)")
                warnings = d.default_label.value_counts().reindex([0, 1], fill_value=0)
                axes[3].bar(["Nhãn 0", "Nhãn 1 · cảnh báo"], warnings.values, color=["#087f83", "#bd252d"])
                axes[3].set(title="Nhãn cảnh báo theo ngưỡng đã lưu", ylabel="Số hồ sơ")
        for ax in axes:
            ax.tick_params(labelsize=8, colors="#566176", length=0, pad=6)
            ax.title.set_fontsize(10)
            ax.title.set_color("#101b33")
            ax.title.set_fontweight("semibold")
            ax.set_axisbelow(True)
            if ax.axison and not ax.images:
                ax.grid(axis="y", color="#edf0f7", linewidth=0.8)
            for spine in ax.spines.values():
                spine.set_color("#dce3ef")
            ax.xaxis.label.set_fontsize(8)
            ax.yaxis.label.set_fontsize(8)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        self.canvas.draw_idle()
