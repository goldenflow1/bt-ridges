from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table

metadata = MetaData()
parcel = Table('parcels', metadata, Column('id', Integer, primary_key=True),
               Column('carrier_id', Integer, nullable=False), Column('reference', String, nullable=False))
scan = Table('scans', metadata, Column('id', Integer, primary_key=True),
             Column('parcel_id', ForeignKey('parcels.id'), nullable=False),
             Column('recorded_at', DateTime(timezone=True), nullable=False),
             Column('depot', String, nullable=False), Column('condition', String, nullable=False))
