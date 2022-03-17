import os

from telegram import Update  # for type hinting
from telegram.ext import Updater, CallbackContext, CommandHandler, MessageHandler, Filters

from src import db_session
from src.models.user import User
from utils import (delete_user_by_username, get_usernames, check_username,
                   create_markup_with_link, revoke_link, set_link)


def start(update: Update, context: CallbackContext):
    if update.message.chat_id < 0:
        return
    username = update.message.from_user.username
    if not username:
        return update.message.reply_text('Для получения доступ в чат Вам необходимо '
                                         'установить никнейм в Telegram и указать его на сайте')
    user_id = update.message.from_user.id
    is_premium, status = check_username(username)
    if status != 'OK':
        return update.message.reply_text('Не удалось проверить наличие премиум-статуса')
    if not is_premium:
        return update.message.reply_text('К сожалению, Вы не имеете премиум-статус, '
                                         'так что Вы не можете быть добавлены в чат')
    with db_session.create_session() as session:
        user = session.query(User).get(username)
        if not user:
            user = User(id=user_id, username=username)
        user.is_premium = True
        session.add(user)
        session.commit()
        if user.invite_link:
            try:
                context.bot.revoke_chat_invite_link(os.getenv('chat_id'), user.invite_link)
                user.invite_link = None
                session.add(user)
                session.commit()
            except Exception as e:
                print(f'An exception occurred: {e}')
        markup, link = create_markup_with_link(context, os.getenv('chat_id'))
        user.invite_link = link
        session.add(user)
        session.commit()
    return context.bot.send_message(user_id,
                                    'Статус премиум Вашего аккаунта подтверждён\n\n'
                                    'Ссылка действует сутки, для получения новой введите /start',
                                    reply_markup=markup)


def handle_user(update: Update, context: CallbackContext):
    with db_session.create_session() as session:
        for user_data in update.message.new_chat_members:
            user = session.query(User).get(user_data.username)
            if not user or not user.is_premium:
                update.message.reply_text('Для того чтобы состоять в данном чате, '
                                          f'нужно авторизоваться через бота @{context.bot.username}')
                context.bot.ban_chat_member(os.getenv('chat_id'), user_data.id)
                if user and user.invite_link:
                    context.bot.revoke_chat_invite_link(os.getenv('chat_id'), user.invite_link)
                delete_user_by_username(user_data.username, session)
        left_user = update.message.left_chat_member
        if left_user:
            delete_user_by_username(left_user.username, session)


def check_users(context: CallbackContext):
    usernames, status = get_usernames(os.getenv('domain'), os.getenv('api_suffix'))
    if status != 'OK':
        return print('Failed to check users')
    chat_id = os.getenv('chat_id')
    if not chat_id:
        return print('There is not chat_id in env')
    with db_session.create_session() as session:
        for user in session.query(User).all():
            if user.username not in usernames:
                context.bot.send_message(chat_id,
                                         f'@{user.username}, статус премиум-аккаунта недействителен')
                context.bot.ban_chat_member(chat_id, user.id)
                revoke_link(context, user, session, chat_id)
                session.delete(user)
                session.commit()
                print(f'{user.username} was kicked from {chat_id}')
            elif not user.is_premium:
                revoke_link(context, user, session, chat_id)
                markup, link = create_markup_with_link(context, chat_id)
                set_link(user, session, link)
                try:
                    context.bot.send_message(user.id,
                                             'Ваш статус премиум был возобновлён\n\n'
                                             'Ссылка действует сутки, для получения новой введите /start',
                                             reply_markup=markup)
                    print(f'{user.username} was invited into {chat_id}')
                except Exception as e:
                    print(f'An exception occurred: {e}')


def start_jobs(dispatcher, bot):
    context = CallbackContext(dispatcher)
    context._bot = bot
    context.job_queue.run_repeating(check_users, 10, 0, context=context, name='check_users')


def main():
    updater = Updater(os.getenv('token'))
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(MessageHandler(Filters.status_update, handle_user))
    start_jobs(updater.dispatcher, updater.bot)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    db_session.global_init(os.getenv('DATABASE_URL'))
    main()
