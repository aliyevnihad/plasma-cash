import rlp
from ethereum import utils

from child_chain.block import Block
from child_chain.transaction import Transaction, UnsignedTransaction
from utils.utils import sign

from .child_chain_service import ChildChainService

from dependency_config import container
import base64

class Client(object):

    def __init__(self,
                 root_chain,
                 token_contract,
                 child_chain=ChildChainService('http://localhost:8546')):
        self.root_chain = root_chain
        self.key = token_contract.account.privateKey
        self.token_contract = token_contract
        self.child_chain = child_chain
        self.child_block_interval = 1000


    ## Token Functions
    def register(self):
        ''' Register a new player and grant 5 cards, for demo purposes'''
        self.token_contract.register()

    def deposit(self, tokenId):
        ''' Deposit happens by a use calling the erc721 token contract '''
        slot = self.root_chain.contract.functions.NUM_COINS().call()
        self.token_contract.deposit(tokenId, slot)
        return self

    ## Plasma Functions

    def start_exit(self, uid, prev_tx_blk_num, tx_blk_num):
        ''' As a user, you declare that you want to exit a coin at slot `uid` at the state which happened at block `tx_blk_num` and you also need to reference a previous block'''
        # TODO The actual proof information should be passed to a user from its previous owners, this is a hacky way of getting the info from the operator which sould be changed in the future after the exiting process is more standardized
        block = self.get_block(tx_blk_num)
        exiting_tx = block.get_tx_by_uid(uid)
        exiting_tx_proof = self.get_proof(tx_blk_num, uid)
        sigs = exiting_tx.sig

        # If the referenced transaction is a deposit transaction then no need 
        prev_tx = '0x0'
        prev_tx_proof = '0x0'
        if prev_tx_blk_num % self.child_block_interval == 0:
            prev_block = self.get_block(prev_tx_blk_num)
            prev_tx = prev_block.get_tx_by_uid(uid)
            prev_tx_proof = self.get_proof(prev_tx_blk_num, uid)

            # Overwrite sigs
            sigs = prev_tx.sig + exiting_tx.sig

        return self.root_chain.start_exit(
                uid,
                rlp.encode(prev_tx, UnsignedTransaction), rlp.encode(exiting_tx, UnsignedTransaction),
                prev_tx_proof, exiting_tx_proof,
                sigs.hex(),
                prev_tx_blk_num, tx_blk_num
        )

    def challenge(self, slot):
        self.root_chain.challenge(slot)
        return self

    def finalize_exits(self):
        self.root_chain.finalize_exits()
        return self
    
    def withdraw(self, slot):
        self.root_chain.withdraw(slot)
        return self

    ## Child Chain Functions

    def submit_block(self):
        block = self.get_current_block()
        block.make_mutable() # mutex for mutability? 
        block.sign(self.key)
        block.make_immutable()
        return self.child_chain.submit_block(rlp.encode(block, Block).hex())

    def send_transaction(self, uid, prev_block, denomination, new_owner):
        new_owner = utils.normalize_address(new_owner)
        tx = Transaction(uid, prev_block, denomination, new_owner)
        tx.make_mutable() # ?
        tx.sign(self.key)
        tx.make_immutable()
        self.child_chain.send_transaction(rlp.encode(tx, Transaction).hex())
        return tx

    def get_current_block(self):
        block = self.child_chain.get_current_block()
        return rlp.decode(utils.decode_hex(block), Block)

    def get_block(self, blknum):
        block = self.child_chain.get_block(blknum)
        return rlp.decode(utils.decode_hex(block), Block)

    def get_proof(self, blknum, uid):
        return base64.b64decode(self.child_chain.get_proof(blknum, uid))


