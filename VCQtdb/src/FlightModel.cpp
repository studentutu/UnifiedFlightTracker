#include "FlightModel.h"

#include <QBrush>
#include <QColor>
#include <QFont>
#include <algorithm>

FlightModel::FlightModel(QObject *parent) : QAbstractTableModel(parent) {}

int FlightModel::rowCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : m_flights.size();
}

int FlightModel::columnCount(const QModelIndex &parent) const {
    return parent.isValid() ? 0 : Col_Count;
}

QVariant FlightModel::headerData(int section, Qt::Orientation orient, int role) const {
    if (role != Qt::DisplayRole) return {};
    if (orient != Qt::Horizontal) return section + 1;
    switch (section) {
        case Col_Callsign:  return QStringLiteral("Callsign");
        case Col_Type:      return QStringLiteral("Type");
        case Col_Altitude:  return QStringLiteral("Alt ft");
        case Col_Speed:     return QStringLiteral("GS kt");
        case Col_Heading:   return QStringLiteral("Hdg°");
        case Col_Distance:  return QStringLiteral("Dist NM");
        case Col_Azimuth:   return QStringLiteral("Az°");
        case Col_Elevation: return QStringLiteral("El°");
        case Col_Source:    return QStringLiteral("Source");
        case Col_Hex:       return QStringLiteral("Hex");
    }
    return {};
}

QVariant FlightModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() < 0 || index.row() >= m_flights.size())
        return {};
    const Flight &f = m_flights[index.row()];

    if (role == Qt::DisplayRole) {
        switch (index.column()) {
            case Col_Callsign:  return f.callsign;
            case Col_Type:      return f.type;
            case Col_Altitude:  return QString::number(qint64(f.altitudeFt + 0.5));
            case Col_Speed:     return QString::number(qint64(f.speedKt   + 0.5));
            case Col_Heading:   return QString::asprintf("%03d", int(f.headingDeg + 0.5) % 360);
            case Col_Distance:  return QString::number(f.distanceNm,   'f', 1);
            case Col_Azimuth:   return QString::number(f.azimuthDeg,   'f', 1);
            case Col_Elevation: return QString::number(f.elevationDeg, 'f', 1);
            case Col_Source:    return f.source;
            case Col_Hex:       return f.hexId;
        }
    }
    // Numeric-aware sort key (used by the proxy).
    if (role == Qt::EditRole) {
        switch (index.column()) {
            case Col_Altitude:  return f.altitudeFt;
            case Col_Speed:     return f.speedKt;
            case Col_Heading:   return f.headingDeg;
            case Col_Distance:  return f.distanceNm;
            case Col_Azimuth:   return f.azimuthDeg;
            case Col_Elevation: return f.elevationDeg;
            case Col_Callsign:  return f.callsign;
            case Col_Type:      return f.type;
            case Col_Source:    return f.source;
            case Col_Hex:       return f.hexId;
        }
    }
    if (role == Qt::ForegroundRole) {
        if (index.column() == Col_Elevation) {
            if (f.elevationDeg < 0)  return QBrush(QColor("#f28b82"));
            if (f.elevationDeg > 30) return QBrush(QColor("#8bc4ff"));
        }
        if (index.column() == Col_Distance) {
            if (f.distanceNm < 5)   return QBrush(QColor("#a5d6a7"));
            if (f.distanceNm > 100) return QBrush(QColor("#9e9e9e"));
        }
    }
    if (role == Qt::TextAlignmentRole) {
        switch (index.column()) {
            case Col_Altitude: case Col_Speed: case Col_Heading:
            case Col_Distance: case Col_Azimuth: case Col_Elevation:
                return int(Qt::AlignRight | Qt::AlignVCenter);
            default: break;
        }
    }
    if (role == Qt::FontRole) {
        switch (index.column()) {
            case Col_Altitude: case Col_Speed: case Col_Heading:
            case Col_Distance: case Col_Azimuth: case Col_Elevation: {
                QFont f2("monospace");
                return f2;
            }
            default: break;
        }
    }
    return {};
}

void FlightModel::setFlights(QList<Flight> flights) {
    std::sort(flights.begin(), flights.end(),
              [](const Flight &a, const Flight &b){ return a.hexId < b.hexId; });
    if (flights.size() == m_flights.size()) {
        m_flights = std::move(flights);
        emit dataChanged(index(0, 0), index(m_flights.size() - 1, Col_Count - 1));
    } else {
        beginResetModel();
        m_flights = std::move(flights);
        endResetModel();
    }
}

int FlightModel::rowForHex(const QString &hex) const {
    for (int i = 0; i < m_flights.size(); ++i)
        if (m_flights[i].hexId == hex) return i;
    return -1;
}

QString FlightModel::hexAt(int row) const {
    if (row < 0 || row >= m_flights.size()) return {};
    return m_flights[row].hexId;
}

const Flight *FlightModel::flightAt(int row) const {
    if (row < 0 || row >= m_flights.size()) return nullptr;
    return &m_flights[row];
}
