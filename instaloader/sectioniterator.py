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
            section = self._data['sections'][self._page_index]
            layout = section.get('layout_content', {})

            if "medias" in layout:
                media_list = layout["medias"]
            elif "one_by_two_item" in layout:
                one_by_two = layout["one_by_two_item"]
                if "clips" in one_by_two and "items" in one_by_two["clips"]:
                    def process_media(item: Dict[str, Any]) -> Dict[str, Any]:
                        m = item["media"]
                        from .structures import Post  
                        if "code" not in m:
                            try:
                                m["code"] = Post.mediaid_to_shortcode(m["pk"])
                            except Exception:
                                m["code"] = None
                        return m
                    media_list = [process_media(item) for item in one_by_two["clips"]["items"] if "media" in item]
                else:
                    media_list = []
            else:
                media_list = []

            if not media_list:
                self._page_index += 1
                self._section_index = 0
                return self.__next__()

            if self._section_index < len(media_list):
                media = media_list[self._section_index]
                self._section_index += 1
                if self._section_index >= len(media_list):
                    self._section_index = 0
                    self._page_index += 1
                return self._media_wrapper(media)
        if self._data.get('more_available'):
            self._page_index, self._section_index, self._data = 0, 0, self._query(self._data.get("next_max_id"))
            return self.__next__()
        raise StopIteration()
