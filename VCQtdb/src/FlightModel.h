#pragma once

#include <QAbstractTableModel>
#include <QList>

#include "Flight.h"

class FlightModel : public QAbstractTableModel {
    Q_OBJECT
public:
    enum Column {
        Col_Callsign,
        Col_Type,
        Col_Altitude,
        Col_Speed,
        Col_Heading,
        Col_Distance,
        Col_Azimuth,
        Col_Elevation,
        Col_Source,
        Col_Hex,
        Col_Count
    };

    explicit FlightModel(QObject *parent = nullptr);

    // QAbstractTableModel
    int      rowCount(const QModelIndex &parent = {}) const override;
    int      columnCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QVariant headerData(int section, Qt::Orientation orient, int role = Qt::DisplayRole) const override;

    // App-facing.
    void setFlights(QList<Flight> flights);
    int  rowForHex(const QString &hex) const;
    QString hexAt(int row) const;
    const Flight *flightAt(int row) const;

private:
    QList<Flight> m_flights;
};
