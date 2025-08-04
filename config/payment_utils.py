"""Payment utilities for random card selection and formatting"""
import random
from config.settings import settings


def get_random_payment_card():
    """Get a random payment card from configured cards"""
    if not settings.bot.payment_cards:
        return None
    return random.choice(settings.bot.payment_cards)


def format_payment_info(card=None):
    """Format payment information for display"""
    if not card:
        card = get_random_payment_card()
    
    if not card:
        return "اطلاعات پرداخت در دسترس نیست"
    
    card_text = f"شماره کارت: `{card.number}`\nنام صاحب حساب: {card.owner}"
    if card.bank:
        card_text += f"\nبانک: {card.bank}"
    
    return card_text