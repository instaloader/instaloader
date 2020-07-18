import base64
import hashlib
import json
from collections import namedtuple
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from .exceptions import InvalidArgumentException
from .instaloadercontext import InstaloaderContext, QueryReturnedBadRequestException

FrozenNodeIterator = namedtuple('FrozenNodeIterator',
                                ['query_hash', 'query_variables', 'query_referer', 'context_username',
                                 'total_index', 'remaining_data'])

T = TypeVar('T')


class NodeIterator(Iterator[T]):
    """
    Iterate the nodes within edges in a GraphQL pagination.

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

    """

    _graphql_page_length = 50

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

    def _query(self, after: Optional[str] = None):
        pagination_variables: Dict[str, Any] = {'first': NodeIterator._graphql_page_length}
        if after is not None:
            pagination_variables['after'] = after
        try:
            return self._edge_extractor(
                self._context.graphql_query(
                    self._query_hash, {**self._query_variables, **pagination_variables}, self._query_referer
                )
            )
        except QueryReturnedBadRequestException:
            new_page_length = int(NodeIterator._graphql_page_length / 2)
            if new_page_length >= 12:
                NodeIterator._graphql_page_length = new_page_length
                self._context.error("HTTP Error 400 (Bad Request) on GraphQL Query. Retrying with shorter page length.",
                                    repeat_at_end=False)
                return self._query()
            else:
                raise

    def __iter__(self):
        return self

    def __next__(self):
        if self._data is None:
            self._data = self._query()
        if self._page_index < len(self._data['edges']):
            node = self._data['edges'][self._page_index]['node']
            self._page_index += 1
            self._total_index += 1
            return self._node_wrapper(node)
        if self._data['page_info']['has_next_page']:
            query_response = self._query(self._data['page_info']['end_cursor'])
            self._page_index = 0
            self._data = query_response
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
            magic_hash = hashlib.blake2b(digest_size=6)
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
            remaining_data=remaining_data,
        )

    def thaw(self, frozen: FrozenNodeIterator):
        """Use this iterator for resuming from earlier iteration."""
        if self._total_index or self._page_index:
            raise InvalidArgumentException("thaw() called on already-used iterator.")
        if (self._query_hash != frozen.query_hash or
                self._query_variables != frozen.query_variables or
                self._query_referer != frozen.query_referer or
                self._context.username != frozen.context_username):
            raise InvalidArgumentException("Mismatching resume information.")
        self._total_index = frozen.total_index
        self._data = frozen.remaining_data
