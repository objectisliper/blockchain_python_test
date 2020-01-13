import hashlib
import json
import os

from textwrap import dedent
from time import time
from uuid import uuid4

from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request


class Blockchain(object):

    def __init__(self):
        """
        Инициализируем свой блокчейн
        """
        self.current_transactions = []
        self.nodes = set()
        self.chain = []

        # Create the genesis block
        self.new_block(previous_hash=1, proof=100)

    def register_node(self, address):
        """
        Добавляем новый узел в список узлов

        :параметр address: <str> Адрес узла, например: 'http://192.168.0.5:5000'
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        """
        Создаем новый блок в нашем Блокчейне


        :параметр proof: <int> proof полученный после использования алгоритма «Доказательство выполнения работы»
        :параметр previous_hash: (Опциональный) <str> Хэш предыдущего Блока
        :return: <dict> New Block
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block),
        }

        # Сбрасываем текущий список транзакций
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Создает новую транзакцию для перехода к следующему замайненному Блоку

        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param amount: <int> Amount
        :return: <int> Индекс блока который будет хранить в себе эту транзакцию
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        Создает a SHA-256 хэш блока

        :параметр block: <dict> Блок
        :return: <str>
        """

        # Мы должны быть уверены что наш Словарь упорядочен, или мы можем непоследовательные хэши
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof):
        """
        Простой алгоритм Proof of Work:
         - Ищем число p' такое, чтобы hash(pp') содержал в себе 4 лидирующих нуля, где p это предыдущий p'
         - p это предыдущий proof, а p' это новый proof

        :параметр last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Проверяем Proof: Содержит ли hash(last_proof, proof) 4 лидирующих нуля?

        :параметр last_proof: <int> предыдущий Proof
        :параметр proof: <int> Текущий Proof
        :return: <bool> True если все верно, иначе False.
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self, chain):
        """
        Определяем, что данный блокчейн прошел проверку

        :параметр chain: <list> Блокчейн
        :return: <bool> True если прошел проверку, иначе False
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # Проверяем, что хэш этого блока корректен
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Проверяем, что алгоритм PoW корректен
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block

            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Это наш алгоритм Консенсуса, он разрешает конфликт путём
        замены нашей цепочки на самую длинную в нашей сети.

        :return: <bool> True если наша цепочка была заменена, False если это не так
        """

        neighbours = self.nodes
        new_chain = None

        # Мы ищем цепочки длиннее наших
        max_length = len(self.chain)

        # Берем все цепочки со всех узлов нашей сети и проверяем их
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Проверяем, что цепочка имеет
                # максимальную длину и она корректна
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Заменяем нашу цепочку, если нашли другую,
        # которая имеет большую длину и является корректной
        if new_chain:
            self.chain = new_chain
            return True

        return False


# Создаем экземпляр нашего узла
app = Flask(__name__)

# Генерируем уникальный глобальный адрес для этого узла
node_identifier = str(uuid4()).replace('-', '')

# Создаем экземпляр Blockchain
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    # Мы запускаем алгоритм PoW для того чтобы найти следующий proof...
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Мы должны получить награду за найденный proof.
    # Если sender = "0", то это означает что данный узел заработал биткойн.
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # Формируем новый блок, путем добавления его в цепочку
    block = blockchain.new_block(proof)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Проверяем, что обязательные поля переданы в POST-запрос
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Создаем новую транзакцию
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT')))
