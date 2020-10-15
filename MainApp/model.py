from MainApp import db
from flask import current_app
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


class stock(db.Model):
    # __tablename__ = 'stock'

    stock_id = db.Column(db.Integer, primary_key=True)
    stock_name = db.Column(db.String, nullable=False, unique=True)
    stock_quantity = db.Column(db.Integer, nullable=False)

    # def __init__(self, stock_name, stock_quantity):
    #     self.stock_name = stock_name
    #     self.stock_quantity = stock_quantity

    # def __repr__(self):
    #     return f''' Stock_ID = {self.stock_id}
    #                 Stock_Name = {self.stock_name}
    #                 Stock_Quantity = {self.stock_quantity}
    #             '''
