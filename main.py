import sys
import os
import signal
import json

from distutils.spawn import find_executable
from textwrap import shorten
from psutil import process_iter
from subprocess import Popen, DEVNULL
from time import sleep

from pytg.sender import Sender
from pytg.receiver import Receiver
from pytg.utils import coroutine
from pytg.exceptions import IllegalResponseException

# SETTINGS
## Telegram CLI
TG_CLI = 'telegram-cli'
TG_CLI_PORT = 44134
TG_CLI_EXECUTABLE = find_executable(TG_CLI)
TG_CLI_PID = None
TG_CLI_TIMEOUT = 20

REQUEST_DELAY = 2  # Time to wait before the next request
SAVE_PATH = './messages/'


def init_tg_cli():
    try:
        p = next(p for p in process_iter()
             if p.name() == 'telegram-cli'
             and p.cmdline()[
                 p.cmdline().index('-P') + 1 == str(TG_CLI_PORT)])
    except:
        print('Running telegram-cli on port {}'.format(str(TG_CLI_PORT)))
        p = Popen([TG_CLI_EXECUTABLE, '--json', '-d', '-P', str(TG_CLI_PORT)])

    global TG_CLI_PID
    TG_CLI_PID = p.pid

    receiver = Receiver(host="localhost", port=TG_CLI_PORT)
    sender = Sender(host="localhost", port=TG_CLI_PORT)
    sender.default_answer_timeout = TG_CLI_TIMEOUT

    return receiver, sender


def answer_yn(question=None):
    """Prints a simple yes or no question and returns bool"""
    while True:
        answer = input(question or 'Are you sure? Y/n').lower()
        if answer == '' or answer == 'y' or answer == 'yes':
            return True
        elif answer == 'n' or answer == 'no':
            return False

        print('Please enter a valid answer (Y/n)')



def menu(title, menu_items, instructions=None):
    """
    Print menu and return chosen menu entry.
    It can take a list of strings or a list of dicts as long
    as the dicts have a 'text' key for each item.

    ['one', 'two', 'three']
    [{'text': 'one', 'other_key': '...'}, {...}]
    """
    separator_len = 64
    print(title)
    print("=" * separator_len)

    if instructions is not None:
        print(instructions)

    if all(isinstance(item, str) for item in menu_items):
        print('\n'.join(['{:>4} - {}'.format(i + 1, item)
            for i, item in enumerate(menu_items)]))

    elif (all(isinstance(item, dict) for item in menu_items) and
          all(['text' in item for item in menu_items])):
        print('\n'.join(['{:>4} - {}'.format(i + 1, item['text'])
            for i, item in enumerate(menu_items)]))
    else:
        raise Exception('Invalid menu definition')

    print('   0 - Exit')
    print('-' * separator_len)
    while True:
        try:
            option = int(input('Enter the option number: '))
            if 0 < option <= len(menu_items):
                return option - 1
            elif option is 0:
                sys.exit()
        except ValueError:
            pass

        print('Please enter a valid option number')


def select_dialog(sender):
    """Ask the user to select which action to perform"""
    dialog_list = sender.dialog_list(999)

    menu_content = [
            '[{}] {}'.format(
                dialog['peer_type']
                    .replace('channel', 'S')  # Supergroups
                    .replace('chat', 'C')
                    .replace('user', 'U')
                    .replace('encr_chat', 'E')  # Encrypted chat
                    .replace('geo_chat', 'G'),
                shorten(dialog['print_name'], width=48, placeholder='...'))
            for dialog in dialog_list]

    dialog_number = menu('Select chat', menu_content)
    dialog_id = dialog_list[dialog_number]['id']
    dialog_name = dialog_list[dialog_number]['print_name']
    return dialog_id, dialog_name


def get_full_history(sender, dialog_id):
    """Download the full history for the selected dialog"""
    page = 0
    limit = 100
    history = []

    print('Downloading messages...')

    while True:
        sleep(REQUEST_DELAY)
        offset = page * limit

        try:
            history[0:0] = sender.history(dialog_id, limit, offset)
            print('.', end=' ', flush=True)
        except IllegalResponseException:
            print('\n{} messages found in selected dialog'.format(len(history)))
            break

        page += 1

    print('')
    return history



def filter_messages_by_user(history, user):
    """Filter messages sent by the specified user in the provided history"""
    own_messages = []

    print('Filtering messages for user {}...'.format(user['username']))

    for message in history:
        if user['id'] == message['from']['id']:
            own_messages.insert(0, message)
            print('x', end='', flush=True)
        else:
            print('.', end='', flush=True)

    print('')

    return own_messages


def write_json_to_file(filename, content):
    """Dumps a dict as JSON to the specified filename"""

    print('Writing to {}'.format(filename))

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as f:
        f.write(json.dumps(content, indent=2))

    print('Done!')


def save_history(save_path, own_messages=False):
    """Download and save the chat history"""

    def get_and_save_history(sender):
        dialog_id, dialog_name = select_dialog(sender)
        history = get_full_history(sender, dialog_id)
        filename = '{}.json'.format(dialog_name[:32])

        if own_messages:
            user = sender.whoami()
            history = filter_messages_by_user(history, user)
            filename = '{}_own.json'.format(dialog_name[:32])

        filename = os.path.join(save_path, filename)

        write_json_to_file(filename, history)

    return get_and_save_history


def delete_messages(sender):
    """
    Delete all user messages

    NOTE: Messages will be deleted only for the user. Other users
    will still be able to see the messages since telegram-cli does
    not have support for completely deleting messages (at least
    for now).
    """
    dialog_id, dialog_name = select_dialog(sender)
    history = get_full_history(sender, dialog_id)
    user = sender.whoami()
    own_messages = filter_messages_by_user(history, user)

    print('The messages you have sent to {} ({}) will be deleted'.format(
        dialog_name, dialog_id))

    if not answer_yn():
        print('Cancelled')
        return

    print('Deleting messages')

    for message in own_messages:
        sender.message_delete(message['id'], forEveryone=True)
        print('.', end='', flush=True)


def main():
    receiver, sender = init_tg_cli()

    menu_content = [
        {
            'text': 'Save full chat history',
            'action': save_history(SAVE_PATH)
        },
        {
            'text': 'Save own messages',
            'action': save_history(SAVE_PATH, own_messages=True)
        },
    ]

    while True:
        choice = menu('Select option', menu_content)

        menu_content[choice]['action'](sender)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\nExit')

    # Close telegram-cli
    os.kill(TG_CLI_PID, signal.SIGTERM)
