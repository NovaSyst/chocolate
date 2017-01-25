
from contextlib import contextmanager
import pickle
import re

import dataset
import filelock
import sqlalchemy

from ..base import Connection

class SQLiteConnection(Connection):
    """Connection to a SQLite database.

    Before calling any method you must explicitly :meth:`lock` the database
    since SQLite does not handle well concurrency.

    We use `dataset <https://dataset.readthedocs.io>`_ under the hood allowing
    us to manage a SQLite database just like a list of dictionaries. Thus no 
    need to predefine any schema nor maintain it explicitly. You can treat this
    database just as a list of dictionaries.

    Args:
        url: Full url to the database, as described in the `SQLAlchemy
            documentation
            <http://docs.sqlalchemy.org/en/latest/core/engines.html#sqlite>`_.
            The url is parsed to find the database path. A lock file will be
            created in the same directory than the database. If in memory
            database is used (``url = "sqlite:///"`` or ``url =
            "sqlite:///:memory:"``) a lock file will be created in the current
            working directory.
        result_table: Table used to store the experiences and their results.
        complementary_table: Table used to store complementary information necessary
            to the optimizer.
    """
    def __init__(self, url, result_table="results", complementary_table="complementary", space_table="space"):
        super(SQLiteConnection, self).__init__()
        if url.endswith("/"):
            raise RuntimeError("Empty database name {}".format(url))

        if url.endswith((" ", "\t")):
            raise RuntimeError("Database name ends with space {}".format(url))

        if not url.startswith("sqlite://"):
            raise RuntimeError("Missing 'sqlite:///' at the begin of url".format(url))

        match = re.search("sqlite:///(.*)", url)
        if match is not None:
            db_path = match.group(1)
        elif url == "sqlite://" or url == "sqlite:///:memory:":
            url = "sqlite:///:memory:"
            db_path = ""
        else:
            raise RuntimeError("Cannot find sqlite db path in {}".format(url))

        self.db = dataset.connect(url)
        self.result_table_name = result_table
        self.complementary_table_name = complementary_table
        self.space_table_name = space_table
        self.results = self.db[self.result_table_name]
        # Initializing with None turns a column into str,
        # ensure float for loss
        self.results.create_column("_loss", sqlalchemy.Float)
        
        self.complementary = self.db[self.complementary_table_name]
        self.space = self.db[self.space_table_name]
        self._lock = filelock.FileLock("{}.lock".format(db_path))

    @contextmanager
    def lock(self, timeout=-1, poll_interval=0.05):
        """Context manager that locks the entire database.

        Args:
            timeout: If the lock could not be acquired in *timeout* seconds
                raises a timeout error. If 0 or less, wait forever.
            poll_interval: Number of seconds between lock acquisition tryouts.

        Raises:
            TimeoutError: Raised if the lock could not be acquired.
        
        Example:
        ::

            conn = SQLiteConnection("sqlite:///temp.db")
            with conn.lock(timeout=5):
                # The database is locked
                all_ = conn.all_results()
                conn.insert({"new_data" : len(all_)})

            # The database is unlocked
        """
        with self._lock.acquire(timeout, poll_interval):
            yield

    def all_results(self):
        """Get a list of all entries of the result table. The order is
        undefined.
        """
        return list(self.results.all())

    def find_results(self, filter):
        """Get a list of all results associated with *filter*. The order is
        undefined.
        """
        return list(self.results.find(**filter))

    def insert_result(self, document):
        """Insert a new *document* in the result table. The columns must not
        be defined nor all present. Any new column will be added to the
        database and any missing column will get value None.
        """
        return self.results.insert(document)

    def update_result(self, filter, values):
        """Update or add *values* of a given row in the result table.

        Args:
            filter: A unique identifier of the row to update.
            value: A mapping of values to update or add.
        """
        filter = filter.copy()
        keys = list(filter.keys())
        filter.update(values)
        return self.results.update(filter, keys)

    def count_results(self):
        """Get the total number of entries in the result table.
        """
        return self.results.count()

    def all_complementary(self):
        """Get all entries of the complementary information table as a list.
        The order is undefined.
        """
        return list(self.complementary.all())

    def insert_complementary(self, document):
        """Insert a new document (row) in the complementary information table.
        """
        return self.complementary.insert(document)

    def find_complementary(self, filter):
        """Find a document (row) from the complementary information table.
        """
        return self.complementary.find_one(**filter)

    def get_space(self):
        """Returns the space used for previous experiments.

        Raises:
        AssertionError: If there are more than one space in the database.
        """
        entry_count = self.space.count()
        if entry_count == 0:
            return None

        assert entry_count == 1, ("Space table unexpectedly contains more than one space.")
        return pickle.loads(self.space.find_one()["space"])

    def insert_space(self, space):
        """Insert a space in the database.

        Raises:
            AssertionError: If a space is already present in the database.
        """
        assert self.space.count() == 0, ("Space table cannot contain more than one space, "
            "clear table first.")
        return self.space.insert({"space" : pickle.dumps(space)})

    def clear(self):
        """Clear all data from the database.
        """
        self.results.drop()
        self.complementary.drop()
        self.space.drop()
        self.results = self.db[self.result_table_name]
        self.complementary = self.db[self.complementary_table_name]
        self.space = self.db[self.space_table_name]