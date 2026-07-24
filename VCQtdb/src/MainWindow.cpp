#include "MainWindow.h"

#include <QAction>
#include <QApplication>
#include <QDockWidget>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QLabel>
#include <QLineEdit>
#include <QMenuBar>
#include <QSplitter>
#include <QStatusBar>
#include <QTableView>
#include <QVBoxLayout>

#include "AltitudeStripChart.h"
#include "FlightModel.h"
#include "KpiBar.h"
#include "PolarSkyView.h"

MainWindow::MainWindow(QUrl baseUrl, TrackerClient::Observer obs, int intervalMs, QWidget *parent)
    : QMainWindow(parent) {
    setWindowTitle("Unified Flight Tracker — Dashboard (Qt/C++)");
    resize(1400, 850);
    applyDarkPalette();

    m_kpi   = new KpiBar(this);
    m_sky   = new PolarSkyView(this);
    m_strip = new AltitudeStripChart(this);

    // Table + filter box.
    m_model  = new FlightModel(this);
    m_proxy  = new QSortFilterProxyModel(this);
    m_proxy->setSourceModel(m_model);
    m_proxy->setFilterCaseSensitivity(Qt::CaseInsensitive);
    m_proxy->setFilterKeyColumn(-1);
    m_proxy->setSortRole(Qt::EditRole);

    m_view = new QTableView(this);
    m_view->setModel(m_proxy);
    m_view->setSortingEnabled(true);
    m_view->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_view->setSelectionMode(QAbstractItemView::SingleSelection);
    m_view->setAlternatingRowColors(true);
    m_view->verticalHeader()->setDefaultSectionSize(22);
    m_view->verticalHeader()->hide();
    auto *hdr = m_view->horizontalHeader();
    hdr->setStretchLastSection(true);
    hdr->setSectionResizeMode(QHeaderView::Interactive);
    const int widths[] = {90, 70, 70, 60, 55, 70, 55, 55, 150, 90};
    for (int i = 0; i < FlightModel::Col_Count; ++i)
        m_view->setColumnWidth(i, widths[i]);

    m_filter = new QLineEdit(this);
    m_filter->setPlaceholderText("filter (callsign, type, hex, source…)");
    connect(m_filter, &QLineEdit::textChanged,
            m_proxy, &QSortFilterProxyModel::setFilterFixedString);

    auto *countLbl = new QLabel("0 aircraft", this);
    countLbl->setStyleSheet("color:#9aa7b5;");
    connect(m_model, &QAbstractItemModel::modelReset, this, [this, countLbl]{
        countLbl->setText(QString("%1 aircraft").arg(m_model->rowCount()));
    });
    connect(m_model, &QAbstractItemModel::dataChanged, this, [this, countLbl]{
        countLbl->setText(QString("%1 aircraft").arg(m_model->rowCount()));
    });

    auto *tableTop = new QHBoxLayout();
    tableTop->setContentsMargins(0,0,0,0);
    tableTop->addWidget(m_filter, 1);
    tableTop->addWidget(countLbl, 0);

    auto *tableBox = new QWidget(this);
    auto *tableLay = new QVBoxLayout(tableBox);
    tableLay->setContentsMargins(6,6,6,6);
    tableLay->setSpacing(4);
    tableLay->addLayout(tableTop);
    tableLay->addWidget(m_view);

    auto *split = new QSplitter(Qt::Horizontal, this);
    split->addWidget(m_sky);
    split->addWidget(tableBox);
    split->setStretchFactor(0, 55);
    split->setStretchFactor(1, 45);
    split->setChildrenCollapsible(false);

    auto *central = new QWidget(this);
    auto *cl = new QVBoxLayout(central);
    cl->setContentsMargins(0,0,0,0);
    cl->setSpacing(4);
    cl->addWidget(m_kpi);
    cl->addWidget(split, 1);
    setCentralWidget(central);

    auto *dock = new QDockWidget("Altitude history (5 min)", this);
    dock->setWidget(m_strip);
    dock->setAllowedAreas(Qt::BottomDockWidgetArea | Qt::TopDockWidgetArea);
    dock->setFeatures(QDockWidget::DockWidgetMovable
                    | QDockWidget::DockWidgetFloatable
                    | QDockWidget::DockWidgetClosable);
    addDockWidget(Qt::BottomDockWidgetArea, dock);

    buildMenu();
    statusBar()->showMessage(
        QString("observer (%1, %2)  r=%3 NM · polling %4/api/flights every %5 s")
            .arg(obs.lat, 0, 'f', 4).arg(obs.lon, 0, 'f', 4)
            .arg(obs.radiusNm, 0, 'f', 0)
            .arg(baseUrl.toString())
            .arg(intervalMs / 1000.0));

    // Wiring.
    connect(m_sky, &PolarSkyView::aircraftPicked, this, &MainWindow::onSkyPick);
    connect(m_view->selectionModel(), &QItemSelectionModel::currentRowChanged,
            this, &MainWindow::onTableSelectionChanged);

    m_client = new TrackerClient(std::move(baseUrl), obs, intervalMs, this);
    connect(m_client, &TrackerClient::flightsReceived, this, &MainWindow::onFlights);
    connect(m_client, &TrackerClient::error, this, &MainWindow::onError);
    m_client->start();
}

MainWindow::~MainWindow() {
    if (m_client) m_client->stop();
}

void MainWindow::applyDarkPalette() {
    QPalette pal;
    pal.setColor(QPalette::Window,          QColor("#0b1420"));
    pal.setColor(QPalette::WindowText,      QColor("#e0e8f0"));
    pal.setColor(QPalette::Base,            QColor("#0f1a26"));
    pal.setColor(QPalette::AlternateBase,   QColor("#14212f"));
    pal.setColor(QPalette::Text,            QColor("#e0e8f0"));
    pal.setColor(QPalette::Button,          QColor("#182535"));
    pal.setColor(QPalette::ButtonText,      QColor("#e0e8f0"));
    pal.setColor(QPalette::Highlight,       QColor("#2f6ea0"));
    pal.setColor(QPalette::HighlightedText, QColor("#ffffff"));
    pal.setColor(QPalette::ToolTipBase,     QColor("#1a2635"));
    pal.setColor(QPalette::ToolTipText,     QColor("#e0e8f0"));
    qApp->setPalette(pal);
    qApp->setStyleSheet(
        "QMainWindow, QDockWidget { background:#0b1420; }"
        "QDockWidget::title { background:#132030; padding:4px 8px; color:#c7d2df;"
        "                     border-bottom:1px solid #23324a; }"
        "QHeaderView::section { background:#14212f; color:#c7d2df; padding:4px 6px;"
        "                       border:0; border-right:1px solid #23324a; }"
        "QTableView { background:#0f1a26; alternate-background-color:#132030;"
        "             selection-background-color:#2f6ea0; gridline-color:#1c2a3b; }"
        "QLineEdit { background:#0f1a26; color:#e0e8f0; border:1px solid #23324a;"
        "            border-radius:4px; padding:4px 6px; }"
        "QMenuBar, QMenu { background:#0b1420; color:#e0e8f0; }"
        "QStatusBar { background:#0b1420; color:#9fb0c2; }"
    );
}

void MainWindow::buildMenu() {
    auto *m = menuBar()->addMenu("&View");
    auto *quitAct = new QAction("&Quit", this);
    quitAct->setShortcut(QKeySequence::Quit);
    connect(quitAct, &QAction::triggered, this, &MainWindow::close);
    m->addAction(quitAct);
}

void MainWindow::onFlights(const QList<Flight> &flights, const QStringList &messages, double elapsedMs) {
    m_kpi->setOk(elapsedMs, messages);
    m_kpi->setFlights(flights);
    m_sky->setFlights(flights);
    m_model->setFlights(flights);
    m_strip->updateFromSnapshot(flights);
}

void MainWindow::onError(const QString &msg) {
    m_kpi->setError(msg);
}

void MainWindow::onSkyPick(const QString &hex) {
    const int srcRow = m_model->rowForHex(hex);
    if (srcRow >= 0) {
        const QModelIndex idx = m_proxy->mapFromSource(m_model->index(srcRow, 0));
        m_view->selectionModel()->setCurrentIndex(
            idx, QItemSelectionModel::SelectCurrent | QItemSelectionModel::Rows);
    }
    m_strip->setSelected(hex, labelFor(hex));
}

void MainWindow::onTableSelectionChanged() {
    const QModelIndex current = m_view->selectionModel()->currentIndex();
    if (!current.isValid()) { m_sky->selectHex({}); m_strip->setSelected({}, {}); return; }
    const int srcRow = m_proxy->mapToSource(current).row();
    const QString hex = m_model->hexAt(srcRow);
    m_sky->selectHex(hex);
    m_strip->setSelected(hex, labelFor(hex));
}

QString MainWindow::labelFor(const QString &hex) const {
    const int row = m_model->rowForHex(hex);
    if (row < 0) return hex;
    const Flight *f = m_model->flightAt(row);
    if (!f) return hex;
    return QString("%1 · %2 · hex %3")
        .arg(f->callsign.isEmpty() ? hex : f->callsign)
        .arg(f->type.isEmpty()     ? QStringLiteral("?") : f->type)
        .arg(f->hexId);
}
