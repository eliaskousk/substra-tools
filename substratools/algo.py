# coding: utf8
import abc
import argparse
import logging
import os
import sys

from substratools import opener, workspace


class Algo(abc.ABC):
    """Abstract base class for defining algo to run on the platform."""

    @abc.abstractmethod
    def train(self, X, y, models, rank):
        """Train algorithm and produce new model.

        Must return a tuple (predictions, model).
        """
        raise NotImplementedError

    @abc.abstractmethod
    def predict(self, X, y, model):
        """Load model and save predictions made on train data.

        Must return predictions.
        """
        raise NotImplementedError

    def dry_run(self, X, y, models, rank):
        """Train model dry run mode."""
        return self.train(X, y, models, rank=0)

    @abc.abstractmethod
    def load_model(self, path):
        """Load model from path."""
        raise NotImplementedError

    @abc.abstractmethod
    def save_model(self, model, path):
        """Save model to path."""
        raise NotImplementedError


class AlgoWrapper(object):
    """Algo wrapper to execute an algo instance on the platform."""

    def __init__(self, interface):
        assert isinstance(interface, Algo)
        self._opener_wrapper = opener.load_from_module()

        self._interface = interface
        self._workspace = workspace.Workspace()

    def _load_models(self, model_names):
        """Load models in-memory from names."""
        # load models from workspace and deserialize them
        models = []
        for name in model_names:
            path = os.path.join(self._workspace.model_folder, name)
            m = self._interface.load_model(path)
            models.append(m)
        return models

    def _save_model(self, model):
        """Save model object to workspace."""
        self._interface.save_model(model,
                                   self._workspace.output_model_filepath)

    def train(self, model_names, rank=0, dry_run=False):
        """Train method wrapper."""
        # load data from opener
        logging.info('loading data from opener')
        X = self._opener_wrapper.get_X(dry_run)
        y = self._opener_wrapper.get_y(dry_run)

        # load models
        logging.info('loading models')
        models = self._load_models(model_names)

        # train new model
        logging.info('training')
        method = (self._interface.train if not dry_run else
                  self._interface.dry_run)
        pred, model = method(X, y, models, rank)

        # serialize output model and save it to workspace
        logging.info('saving output model')
        self._save_model(model)

        # save prediction
        logging.info('saving prediction')
        self._opener_wrapper.save_pred(pred)

        return pred, model

    def predict(self, model_name, dry_run=False):
        """Predict method wrapper."""
        # load data from opener
        logging.info('loading data from opener')
        X = self._opener_wrapper.get_X(dry_run)
        y = self._opener_wrapper.get_y(dry_run)

        # load models
        logging.info('loading models')
        models = self._load_models([model_name])

        # get predictions
        logging.info('predicting')
        pred = self._interface.predict(X, y, models[0])

        # save prediction
        logging.info('saving prediction')
        self._opener_wrapper.save_pred(pred)

        return pred


def _generate_cli(algo_wrapper):
    """Helper to generate a command line interface client."""

    def _train(args):
        algo_wrapper.train(args.models, args.rank, args.dry_run)

    def _predict(args):
        algo_wrapper.predict(args.model, args.dry_run)

    parser = argparse.ArgumentParser()
    parsers = parser.add_subparsers()

    train_parser = parsers.add_parser('train')
    train_parser.add_argument(
        'models', type=str, nargs='*')
    train_parser.add_argument(
        '-d', '--dry-run', action='store_true', default=False)
    train_parser.add_argument(
        '-r', '--rank', type=int, default=0)
    train_parser.set_defaults(func=_train)

    predict_parser = parsers.add_parser('predict')
    predict_parser.add_argument(
        'model', type=str)
    predict_parser.add_argument(
        '-d', '--dry-run', action='store_true', default=False)
    predict_parser.set_defaults(func=_predict)
    return parser


def execute(interface, sysargs=None):
    """Launch algo command line interface."""
    algo_wrapper = AlgoWrapper(interface)
    logging.basicConfig(filename=algo_wrapper._workspace.log_path,
                        level=logging.DEBUG)

    cli = _generate_cli(algo_wrapper)

    sysargs = sysargs if sysargs is not None else sys.argv[1:]
    logging.debug('launching command with: {}'.format(sysargs))
    args = cli.parse_args(sysargs)
    args.func(args)
    return args