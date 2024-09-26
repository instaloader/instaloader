from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

from .instaloadercontext import InstaloaderContext

T = TypeVar('T')


class SectionIterator(Iterator[T]):
    """Iterator for the new 'sections'-style responses.

    .. versionadded:: 4.9"""
    def __init__(self,
                 context: InstaloaderContext,
                 sections_extractor: Callable[[Dict[str, Any]], Dict[str, Any]],
                 media_wrapper: Callable[[Dict], T],
                 query_path: str,
                 first_data: Optional[Dict[str, Any]] = None):
        self._context = context
        self._sections_extractor = sections_extractor
        self._media_wrapper = media_wrapper
        self._query_path = query_path
        self._data = first_data or self._query()
        self._page_index = 0
        self._section_index = 0

    def __iter__(self):
        return self

    def _query(self, max_id: Optional[str] = None) -> Dict[str, Any]:
        pagination_variables = {"max_id": max_id} if max_id is not None else {}
        return self._sections_extractor(
            self._context.get_json(self._query_path, params={"__a": 1, "__d": "dis", **pagination_variables})
        )

    def __next__(self) -> T:
        if self._page_index < len(self._data['sections']):
            media = self._data['sections'][self._page_index]['layout_content']['medias'][self._section_index]['media']
            self._section_index += 1
            if self._section_index >= len(self._data['sections'][self._page_index]['layout_content']['medias']):
                self._section_index = 0
                self._page_index += 1
            return self._media_wrapper(media)
        if self._data['more_available']:
            self._page_index, self._section_index, self._data = 0, 0, self._query(self._data["next_max_id"])
            return self.__next__()
        raise StopIteration()
