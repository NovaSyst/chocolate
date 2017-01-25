
from collections import Mapping, Sequence

from .space import Space 

class Connection(object):
    """Abstract connection class that defines the database connection API.
    """
    def lock(self):
        raise NotImplementedError

    def all_results(self):
        raise NotImplementedError

    def find_results(self, filter):
        raise NotImplementedError

    def insert_result(self, entry):
        raise NotImplementedError

    def update_result(self, entry, value):
        raise NotImplementedError

    def count_results(self):
        raise NotImplementedError

    def all_complementary(self):
        raise NotImplementedError

    def insert_complementary(self, document):
        raise NotImplementedError

    def find_complementary(self, filter):
        raise NotImplementedError

    def get_space(self):
        raise NotImplementedError

    def insert_space(self, space):
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError

class SearchAlgorithmMixin(object):
    def __init__(self, connection, space=None, clear_db=False):
        if space is not None and not isinstance(space, Space):
            space = Space(space)

        self.conn = connection
        with self.conn.lock():
            db_space = self.conn.get_space()
            print(db_space)

            if space is None and db_space is None:
                raise RuntimeError("The database does not contain any space, please provide one through"
                    "the 'space' argument")
            elif space is not None and space != db_space and clear_db is False:
                raise RuntimeError("The provided space and database space are different. To overwrite"
                    "the space contained in the database set the 'clear_db' argument")
            elif space is not None and space != db_space and clear_db is True:
                self.conn.clear()
                self.conn.insert_space(space)
            elif space is not None and db_space is None:
                self.conn.insert_space(space)
            elif space is None and db_dpace is not None:
                space = db_space

        self.space = db_space


    def update(self, token, values):
        """Update the loss of the parameters associated with *token*.

        Args:
            token: A token generated by the sampling algorithm for the current
                parameters
            values: The loss of the current parameter set.

        """
        # Check and standardize values type
        if isinstance(values, Sequence):
            raise NotImplementedError("Cross-validation is not yet supported in DB")

        if isinstance(values, Sequence) and not isinstance(values[0], Mapping):
            raise NotImplementedError("Cross-validation is not yet supported in DB")
            values = [{"_loss" : v, "split_" : i} for i, v in enumerate(values)]
        elif not isinstance(values, Mapping):
            values = [{"_loss" : values}]
        elif isinstance(values, Mapping):
            values = [values]

        with self.conn.lock():
            if len(values) > 1:
                orig = self.conn.find_results(token)[0]
                orig = {k: orig[k] for k in self.space.column_names()}

            result = list()
            self.conn.update_result(token, values[0])
            for v in values[1:]:
                document = orig.copy()
                document.update(v)
                document.update(token)
                r = self.conn.insert_result(document)
                result.append(r)
            
        return result