import base64
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from lzma import LZMAError
from typing import Any, Callable, Dict, Iterator, NamedTuple, Optional, Tuple, TypeVar

from .exceptions import InvalidArgumentException, QueryReturnedBadRequestException
from .instaloadercontext import InstaloaderContext

FrozenNodeIterator = NamedTuple('FrozenNodeIterator',
                                [('query_hash', str),
                                 ('query_variables', Dict),
                                 ('query_referer', Optional[str]),
                                 ('context_username', Optional[str]),
                                 ('total_index', int),
                                 ('best_before', Optional[float]),
                                 ('remaining_data', Optional[Dict])])
FrozenNodeIterator.__doc__ = \
    """A serializable representation of a :class:`NodeIterator` instance, saving its iteration state."""
FrozenNodeIterator.query_hash.__doc__ = """The GraphQL ``query_hash`` parameter."""
FrozenNodeIterator.query_variables.__doc__ = """The GraphQL ``query_variables`` parameter."""
FrozenNodeIterator.query_referer.__doc__ = """The HTTP referer used for the GraphQL query."""
FrozenNodeIterator.context_username.__doc__ = """The username who created the iterator, or ``None``."""
FrozenNodeIterator.total_index.__doc__ = """Number of items that have already been returned."""
FrozenNodeIterator.best_before.__doc__ = """Date when parts of the stored nodes might have expired."""
FrozenNodeIterator.remaining_data.__doc__ = \
    """The already-retrieved, yet-unprocessed ``edges`` and the ``page_info`` at time of freezing."""


T = TypeVar('T')


class NodeIterator(Iterator[T]):
    """
    Iterate the nodes within edges in a GraphQL pagination. Instances of this class are returned by many (but not all)
    of Instaloader's :class:`Post`-returning functions (such as :meth:`Profile.get_posts` etc.).

    What makes this iterator special is its ability to freeze/store its current state, e.g. to interrupt an iteration,
    and later thaw/resume from where it left off.

    You can freeze a NodeIterator with :meth:`NodeIterator.freeze`::

       post_iterator = profile.get_posts()
       try:
           for post in post_iterator:
               do_something_with(post)
       except KeyboardInterrupt:
           save("resume_information.json", post_iterator.freeze())

    and later reuse it with :meth:`NodeIterator.thaw` on an equally-constructed NodeIterator::

       post_iterator = profile.get_posts()
       post_iterator.thaw(load("resume_information.json"))

    A :class:`FrozenNodeIterator` can only be thawn with a matching NodeIterator, i.e. a NodeIterator instance that has
    been constructed with the same parameters as the instance that is represented by the :class:`FrozenNodeIterator` in
    question. This is to ensure that an iteration cannot be resumed in a wrong, unmatching loop. As a quick way to
    distinguish iterators that are saved e.g. in files, there is the :attr:`NodeIterator.magic` string: Two
    NodeIterators are matching if and only if they have the same magic.

    See also :func:`resumable_iteration` for a high-level context manager that handles a resumable iteration.
    """

    _graphql_page_length = 50
    _shelf_life = timedelta(days=29)

    def __init__(self,
                 context: InstaloaderContext,
                 query_hash: str,
                 edge_extractor: Callable[[Dict[str, Any]], Dict[str, Any]],
                 node_wrapper: Callable[[Dict], T],
                 query_variables: Optional[Dict[str, Any]] = None,
                 query_referer: Optional[str] = None,
                 first_data: Optional[Dict[str, Any]] = None):
        self._context = context
        self._query_hash = query_hash
        self._edge_extractor = edge_extractor
        self._node_wrapper = node_wrapper
        self._query_variables = query_variables if query_variables is not None else {}
        self._query_referer = query_referer
        self._data = first_data
        self._page_index = 0
        self._total_index = 0
        self._best_before = (None if first_data is None else
                             datetime.now() + NodeIterator._shelf_life)

    def _query(self, after: Optional[str] = None) -> Dict:
        pagination_variables = {'first': NodeIterator._graphql_page_length}  # type: Dict[str, Any]
        if after is not None:
            pagination_variables['after'] = after
        try:
            data = self._edge_extractor(
                self._context.graphql_query(
                    self._query_hash, {**self._query_variables, **pagination_variables}, self._query_referer
                )
            )
            self._best_before = datetime.now() + NodeIterator._shelf_life
            return data
        except QueryReturnedBadRequestException:
            new_page_length = int(NodeIterator._graphql_page_length / 2)
            if new_page_length >= 12:
                NodeIterator._graphql_page_length = new_page_length
                self._context.error("HTTP Error 400 (Bad Request) on GraphQL Query. Retrying with shorter page length.",
                                    repeat_at_end=False)
                return self._query(after)
            else:
                raise

    def __iter__(self):
        return self

    def __next__(self) -> T:
        if self._data is None:
            self._data = self._query()
        if self._page_index < len(self._data['edges']):
            node = self._data['edges'][self._page_index]['node']
            page_index, total_index = self._page_index, self._total_index
            try:
                self._page_index += 1
                self._total_index += 1
            except KeyboardInterrupt:
                self._page_index, self._total_index = page_index, total_index
                raise
            return self._node_wrapper(node)
        if self._data['page_info']['has_next_page']:
            query_response = self._query(self._data['page_info']['end_cursor'])
            page_index, data = self._page_index, self._data
            try:
                self._page_index = 0
                self._data = query_response
            except KeyboardInterrupt:
                self._page_index, self._data = page_index, data
                raise
            return self.__next__()
        raise StopIteration()

    @property
    def count(self) -> Optional[int]:
        """The ``count`` as returned by Instagram. This is not always the total count this iterator will yield."""
        return self._data.get('count') if self._data is not None else None

    @property
    def total_index(self) -> int:
        """Number of items that have already been returned."""
        return self._total_index

    @property
    def magic(self) -> str:
        """Magic string for easily identifying a matching iterator file for resuming (hash of some parameters)."""
        if 'blake2b' not in hashlib.algorithms_available:
            magic_hash = hashlib.new('sha224')
        else:
            # Use blake2b when possible, i.e. on Python >= 3.6.
            magic_hash = hashlib.blake2b(digest_size=6)  # type:ignore  # pylint: disable=no-member
        magic_hash.update(json.dumps(
            [self._query_hash, self._query_variables, self._query_referer, self._context.username]
        ).encode())
        return base64.urlsafe_b64encode(magic_hash.digest()).decode()

    def freeze(self) -> FrozenNodeIterator:
        """Freeze the iterator for later resuming."""
        remaining_data = None
        if self._data is not None:
            remaining_data = {**self._data,
                              'edges': (self._data['edges'][(max(self._page_index - 1, 0)):])}
        return FrozenNodeIterator(
            query_hash=self._query_hash,
            query_variables=self._query_variables,
            query_referer=self._query_referer,
            context_username=self._context.username,
            total_index=max(self.total_index - 1, 0),
            best_before=self._best_before.timestamp() if self._best_before else None,
            remaining_data=remaining_data,
        )

    def thaw(self, frozen: FrozenNodeIterator) -> None:
        """
        Use this iterator for resuming from earlier iteration.

        :raises InvalidArgumentException:
           If

           - the iterator on which this method is called has already been used, or
           - the given :class:`FrozenNodeIterator` does not match, i.e. belongs to a different iteration.
        """
        if self._total_index or self._page_index:
            raise InvalidArgumentException("thaw() called on already-used iterator.")
        if (self._query_hash != frozen.query_hash or
                self._query_variables != frozen.query_variables or
                self._query_referer != frozen.query_referer or
                self._context.username != frozen.context_username):
            raise InvalidArgumentException("Mismatching resume information.")
        self._total_index = frozen.total_index
        self._best_before = datetime.fromtimestamp(frozen.best_before) if frozen.best_before else None
        self._data = frozen.remaining_data


@contextmanager
def resumable_iteration(context: InstaloaderContext,
                        iterator: Iterator,
                        load: Callable[[InstaloaderContext, str], Any],
                        save: Callable[[FrozenNodeIterator, str], None],
                        format_path: Callable[[str], str],
                        check_bbd: bool = True,
                        enabled: bool = True) -> Iterator[Tuple[bool, int]]:
    """
    High-level context manager to handle a resumable iteration that can be interrupted with a KeyboardInterrupt.

    It can be used as follows to automatically load a previously-saved state into the iterator, save the iterator's
    state when interrupted, and delete the resume file upon completion::

       post_iterator = profile.get_posts()
       with resumable_iteration(
               context=L.context,
               iterator=post_iterator,
               load=lambda _, path: FrozenNodeIterator(**json.load(open(path))),
               save=lambda fni, path: json.dump(fni._asdict(), open(path, 'w')),
               format_path=lambda magic: "resume_info_{}.json".format(magic)
       ) as (is_resuming, start_index):
           for post in post_iterator:
               do_something_with(post)

    It yields a tuple (is_resuming, start_index).

    When the passed iterator is not a :class:`NodeIterator`, it behaves as if ``resumable_iteration`` was not used,
    just executing the inner body.

    :param context: The :class:`InstaloaderContext`.
    :param iterator: The fresh :class:`NodeIterator`.
    :param load: Loads a FrozenNodeIterator from given path. The object is ignored if it has a different type.
    :param save: Saves the given FrozenNodeIterator to the given path.
    :param format_path: Returns the path to the resume file for the given magic.
    :param check_bbd: Whether to check the best before date and reject an expired FrozenNodeIterator.
    :param enabled: Set to False to disable all functionality and simply execute the inner body.
    """
    if not enabled or not isinstance(iterator, NodeIterator):
        yield False, 0
        return
    is_resuming = False
    start_index = 0
    resume_file_path = format_path(iterator.magic)
    resume_file_exists = os.path.isfile(resume_file_path)
    if resume_file_exists:
        try:
            fni = load(context, resume_file_path)
            if not isinstance(fni, FrozenNodeIterator):
                raise InvalidArgumentException("Invalid type.")
            if check_bbd and fni.best_before and datetime.fromtimestamp(fni.best_before) < datetime.now():
                raise InvalidArgumentException("\"Best before\" date exceeded.")
            iterator.thaw(fni)
            is_resuming = True
            start_index = iterator.total_index
            context.log("Resuming from {}.".format(resume_file_path))
        except (InvalidArgumentException, LZMAError, json.decoder.JSONDecodeError) as exc:
            context.error("Warning: Not resuming from {}: {}".format(resume_file_path, exc))
    try:
        yield is_resuming, start_index
    except KeyboardInterrupt:
        os.makedirs(os.path.dirname(resume_file_path), exist_ok=True)
        save(iterator.freeze(), resume_file_path)
        context.log("\nSaved resume information to {}.".format(resume_file_path))
        raise
    if resume_file_exists:
        os.unlink(resume_file_path)
        context.log("Iteration complete, deleted resume information file {}.".format(resume_file_path))
