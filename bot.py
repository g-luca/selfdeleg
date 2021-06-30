import subprocess
import os
import json
import time
from datetime import datetime
import socket
import configparser
import asyncio
import logging
import logging.handlers as handlers


logger = logging.getLogger('valcontrol')
logger.setLevel(logging.DEBUG)

logHandler = handlers.TimedRotatingFileHandler(
    'logs/debug.log', when='midnight', interval=1)
logHandler.suffix = "%Y-%m-%d"
logHandler.setLevel(logging.DEBUG)
logger.addHandler(logHandler)


config = configparser.ConfigParser()
config.read("config.ini")

DEBUG_WATCH_ONLY = int(config["Debug"]["DEBUG_WATCH_ONLY"])

# Validator settings
USER_ADDRESS = str(config["Validator"]["USER_ADDRESS"])
VALIDATOR_ADDRESS = str(config["Validator"]["VALIDATOR_ADDRESS"])
DELEGATE_ADDRESS = str(config["Validator"]["DELEGATE_ADDRESS"])
REDELEGATE_AT = float(config["Validator"]["REDELEGATE_AT"])
TRANSACTION_FEES = str(config["Validator"]["TRANSACTION_FEES"])
MINIMUM_BALANCE = float(config["Validator"]["MINIMUM_BALANCE"])


KEY_NAME = str(config["Validator"]["KEY_NAME"])
KEY_BACKEND = str(config["Validator"]["KEY_BACKEND"])


CHAIN_ID = str(config["Validator"]["CHAIN_ID"])
DEFAULT_NODE_ADDRESS = str(config["Validator"]["DEFAULT_NODE_ADDRESS"])
DEFAULT_NODE_PORT = str(config["Validator"]["DEFAULT_NODE_PORT"])
DEFAULT_NODE = str(DEFAULT_NODE_ADDRESS + ":" + DEFAULT_NODE_PORT)


REFRESH_MINUTES = float(config["Validator"]["REFRESH_MINUTES"])
# ----------------------


# Command Balance
COMMAND_GET_BALANCE = 'desmos q bank balances {} --node {} -o json'.format(
    USER_ADDRESS, DEFAULT_NODE)

# Command Redelegate
COMMAND_REDELEGATE = 'desmos tx staking delegate {} --from {} --keyring-backend {} REPLACE_AMOUNT --fees {} --node {} --chain-id {} --yes'.format(
    VALIDATOR_ADDRESS, KEY_NAME, KEY_BACKEND, TRANSACTION_FEES, DEFAULT_NODE, CHAIN_ID)

# Command Rewards
COMMAND_GET_REWARDS_BALANCE = 'desmos q distribution rewards {} {}  -o json --node {}'.format(
    USER_ADDRESS, VALIDATOR_ADDRESS, DEFAULT_NODE)


COMMAND_WITHDRAW_REWARDS = 'desmos tx distribution withdraw-rewards {} --commission --from {} --keyring-backend {} --fees {} --chain-id {} --node {} --yes'.format(
    VALIDATOR_ADDRESS, KEY_NAME, KEY_BACKEND, TRANSACTION_FEES, CHAIN_ID, DEFAULT_NODE)


# Command Commissions
COMMAND_GET_COMMISSION_BALANCE = 'desmos q distribution commission {}  -o json --node {}'.format(
    VALIDATOR_ADDRESS, DEFAULT_NODE)

# --------------------------


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Execute a shell commands (for desmos cli)
def cmd(cmd):
    try:
        return subprocess.run(
            [cmd], shell=True, stdout=subprocess.PIPE).stdout.decode()
    except subprocess.CalledProcessError as e:
        print("command error")
        return False


class Desmosbot:
    started_at = datetime.now()
    total_redelegated = 0

    balance = 0
    reward = 0
    commission = 0

    UDARIC = 1000000

    def __init__(self):
        self.update()

    def updateBalance(self):
        try:
            balance_raw = cmd(COMMAND_GET_BALANCE)
            balance = json.loads(balance_raw)
            amount = float(
                balance['balances'][0]['amount']) / self.UDARIC
            self.balance = float(amount)
        except:
            print("Error updating balance")

    def updateValidatorReward(self):
        try:
            reward_balance_raw = cmd(COMMAND_GET_REWARDS_BALANCE)
            reward_balance = json.loads(reward_balance_raw)
            reward_amount = float(
                reward_balance['rewards'][0]['amount']) / self.UDARIC
            self.reward = float(reward_amount)
        except:
            print("Error updating rewards")

    def updateValidatorCommission(self):
        try:
            commission_balance_raw = cmd(COMMAND_GET_COMMISSION_BALANCE)
            commission_balance = json.loads(commission_balance_raw)
            commission_amount = float(
                commission_balance['commission'][0]['amount']) / self.UDARIC
            self.commission = float(commission_amount)
        except:
            print("Error updating commissions")

    def update(self):
        self.updateBalance()
        self.updateValidatorReward()
        self.updateValidatorCommission()

    # REWARDS
    def withdrawRewards(self):
        if(self.reward >= REDELEGATE_AT):
            print()
            tx_success = self.tx_withdrawRewards()
            if(tx_success):
                return self.reward
        else:
            print(" > rewards under " + str(REDELEGATE_AT) + " DARIC")
        return 0

    # WITHDRAW REWARDS TRANSACTION
    def tx_withdrawRewards(self):
        print(bcolors.WARNING + "Withdrawing rewards..." + bcolors.ENDC)
        withdraw_success = cmd(COMMAND_WITHDRAW_REWARDS)
        return len(withdraw_success) > 0

    # REDELEGATION LOGIC

    def redelegate(self):
        now = str(datetime.now()) + ":"

        total_rewards_withdrawn: float = 0
        # Withdraw commission and
        if(self.commission + self.reward >= REDELEGATE_AT and not DEBUG_WATCH_ONLY):
            success = self.tx_withdrawRewards()
            if(success):
                total_rewards_withdrawn = self.commission + self.reward
                logger.info(now+"Withdrwawn Rewards and Commissions for " +
                            str(total_rewards_withdrawn) + "DARIC")

        amount_to_redelegate: float = float(
            self.balance) + float(total_rewards_withdrawn) - float(MINIMUM_BALANCE)
        if(amount_to_redelegate >= float(REDELEGATE_AT)):

            if (not DEBUG_WATCH_ONLY):
                self.tx_redelegate(amount_to_redelegate)
                logger.info(now+"withdrawn " +
                            str(amount_to_redelegate) + "DARIC")

            self.total_redelegated += amount_to_redelegate
            print(amount_to_redelegate)
            logger.info(now+"Total redelegations " +
                        str(self.total_redelegated) + "DARIC")

        else:
            print("Rewards and Commissions under " +
                  str(REDELEGATE_AT) + " DARIC")

    # REDELEGATING TRANSACTION

    def tx_redelegate(self, amount_in_daric: float):
        print(bcolors.WARNING + "Redelegating..." + bcolors.ENDC)
        amount_str = str(amount_in_daric * self.UDARIC) + "udaric"
        cmdComplete = COMMAND_REDELEGATE.replace('REPLACE_AMOUNT', amount_str)
        redelegate_success = cmd(cmdComplete)
        if(redelegate_success == "cancelled transaction"):
            return False
        return True


async def main():
    print("starting...")
    if(MINIMUM_BALANCE < 1):
        print("\n\n Configuration MINIMUM_BALANCE MUST BE > 1 !!!\n\n")
        raise "MINIMUM_BALANCE ERROR"
    bot = Desmosbot()
    os.system("clear")

    while(True):
        now = datetime.now()
        print("Started at: " + bcolors.OKCYAN +
              bot.started_at.strftime("%H:%M:%S") + bcolors.ENDC)
        print("Total Redelegations: " + bcolors.OKGREEN +
              str(bot.total_redelegated) + " DARIC" + bcolors.ENDC)

        print("\nLast update: " + bcolors.OKCYAN +
              now.strftime("%H:%M:%S") + bcolors.ENDC)

        print("\n"+bcolors.OKGREEN + "Balance: " +
              bcolors.ENDC + str(bot.balance) + " DARIC")
        print(bcolors.OKGREEN + "Reward: " +
              bcolors.ENDC + str(bot.reward) + " DARIC")
        print(bcolors.OKGREEN + "Commissions: " +
              bcolors.ENDC + str(bot.commission) + " DARIC")

        bot.update()  # update balance, commissions, rewards
        bot.redelegate()

        print(bcolors.OKCYAN +
              "\n\nSleeping... ({}m)".format(REFRESH_MINUTES) + bcolors.ENDC)

        time.sleep(REFRESH_MINUTES * 60)
        os.system("clear")


asyncio.run(main())
