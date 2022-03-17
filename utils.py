import os
import requests
from json import JSONDecodeError

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import CallbackContext
from datetime import datetime, timedelta
import tzlocal

from src.models.user import User


def get_usernames(domain: str, api_suffix: str) -> tuple:
    url = '/'.join([domain.rstrip('/'), api_suffix.lstrip('/')])
    response = requests.get(url, params={'getAllUserId': 1})
    try:
        return [x.lstrip('@') for x in response.json()], 'OK'
    except JSONDecodeError:
        print(f'Failed to decode response received from API: {url}')
    except ValueError:
        print(f'Failed to convert str values into int')
    return [], 'ERROR'


def check_username(username: str) -> tuple:
    domain, api_suffix = os.getenv('domain'), os.getenv('api_suffix')
    if not domain or not api_suffix:
        print('Domain and/or api_suffix vars are missed in env')
    usernames, status = get_usernames(domain, api_suffix)
    return username in usernames, status


def delete_user_by_username(username: str, session):
    user = session.query(User).get(username)
    if user:
        session.delete(user)
        session.commit()


def create_markup_with_link(context: CallbackContext, chat_id: int):
    dt = datetime.now(tzlocal.get_localzone()) + timedelta(hours=24)
    link = context.bot.create_chat_invite_link(chat_id, member_limit=1, expire_date=dt)
    return (InlineKeyboardMarkup([[InlineKeyboardButton('Войти в чат', url=link.invite_link)]]),
            link.invite_link)


def revoke_link(context, user, session, chat_id: int):
    if not user.invite_link:
        return
    try:
        context.bot.revoke_chat_invite_link(chat_id, user.invite_link)
        user.invite_link = None
        session.add(user)
        session.commit()
    except BadRequest:
        pass


def set_link(user, session, link: str):
    user.invite_link = link
    session.add(user)
    session.commit()