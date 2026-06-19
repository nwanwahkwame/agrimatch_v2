from fastapi import Request

from api.payment_gateway import PaymentGateway
from ingestion.alert_engine import AlertEngine
from ingestion.ussd_handler import USSDHandler
from models.byproduct_marketplace import ByproductMarketplace
from models.cooperative_logistics import CooperativeLogistics
from models.crop_recommender import CropRecommender
from models.delay_classifier import HarvestDelayClassifier
from models.logistics_cost import LogisticsCostModel
from models.lstm_predictor import LSTMPredictor
from models.matchmaking_engine import MatchmakingEngine
from models.strategy_generator import StrategyGenerator
from models.xgboost_predictor import XGBoostPredictor


def get_xgb(request: Request) -> XGBoostPredictor:
    return request.app.state.xgb_predictor


def get_lstm(request: Request) -> LSTMPredictor:
    return request.app.state.lstm_predictor


def get_delay_clf(request: Request) -> HarvestDelayClassifier:
    return request.app.state.delay_clf


def get_recommender(request: Request) -> CropRecommender:
    return request.app.state.recommender


def get_strategy(request: Request) -> StrategyGenerator:
    return request.app.state.strategy


def get_matcher(request: Request) -> MatchmakingEngine:
    return request.app.state.matcher


def get_coop(request: Request) -> CooperativeLogistics:
    return request.app.state.coop


def get_byproduct(request: Request) -> ByproductMarketplace:
    return request.app.state.byproduct


def get_alerts(request: Request) -> AlertEngine:
    return request.app.state.alerts


def get_logistics(request: Request) -> LogisticsCostModel:
    return request.app.state.logistics


def get_payment_gateway(request: Request) -> PaymentGateway:
    return request.app.state.payment_gateway


def get_ussd_handler(request: Request) -> USSDHandler:
    return request.app.state.ussd_handler
