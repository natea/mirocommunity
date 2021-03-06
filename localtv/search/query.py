import operator

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from haystack.query import SearchQuerySet, SQ

from tagging.models import Tag
from localtv.models import Feed, Category, SavedSearch
from localtv.playlists.models import Playlist
from localtv.search import shlex


class SmartSearchQuerySet(SearchQuerySet):
    """
    Implements an auto_query method which supports the following keywords on
    top of :class:`haystack.query.SearchQuerySet`\ 's basic functionality:

    * playlist:#
    * playlist:user/slug
    * category:#
    * category:name
    * category:slug
    * user:#
    * user:username
    * feed:#
    * feed:name
    * search:#
    * search:query string
    * tag:name
    * {one of these terms}
    * -"not this term"

    """
    def tokenize(self, query):
        or_stack = []
        negative = False

        while query:
            try:
                lex = shlex.shlex(query, posix=True, locale=True)
                lex.commenters = '' # shlex has a crazy interface
                lex.wordchars = u'-:/_'
                tokens = list(lex)
                break
            except ValueError, e:
                if e.args[0] == 'No closing quotation':
                    # figure out what kind of quote we missed
                    double_count = sum(1 for c in query if c == '"')
                    if double_count % 2: # odd
                        index = query.rfind('"')
                    else:
                        index = query.rfind("'")
                    query = query[:index] + query[index+1:]
                else:
                    raise

        if not query:
            raise StopIteration

        for token in tokens:
            if token == '-':
                if not or_stack:
                    if negative:
                        negative = False
                    else:
                        negative = True
            elif token == '{':
                negative = False
                or_stack.append([])
            elif token == '}':
                negative = False
                last_or = or_stack.pop()
                if not or_stack:
                    yield last_or
                else:
                    or_stack[-1].append(last_or)
            else:
                if token[0] in '\'"':
                    token = token[1:-1]
                if negative and isinstance(token, basestring):
                    negative = False
                    token = '-' + token
                if or_stack:
                    or_stack[-1].append(token)
                else:
                    yield token
        while or_stack:
            yield or_stack.pop()

    def _get_object(self, model, token, *fields):
        """
        Tries various fields to get an object.

        """
        default_kwargs = {}
        try:
            model._meta.get_field_by_name('site')
        except Exception:
            pass
        else:
            default_kwargs['site'] = Site.objects.get_current()
        if 'pk' not in fields:
            fields = fields + ('pk',)

        for field in fields:
            methods = ['exact']
            if field != 'pk':
                methods.append('iexact')
            for method in methods:
                kwargs = default_kwargs.copy()
                kwargs['%s__%s' % (field, method)] = token
                try:
                    return model.objects.get(**kwargs)
                except (model.DoesNotExist, ValueError):
                    pass

    def _tokens_to_sq(self, tokens):
        """
        Takes a list of tokens and returns a single SQ instance representing
        those tokens, or ``None`` if no valid tokens were supplied.

        """
        from localtv.search.utils import _exact_q
        sq_list = []
        for token in tokens:
            if isinstance(token, basestring):
                negated = False
                if token[0] == '-':
                    negated = True
                    token = token[1:]
                if ':' not in token:
                    sq = SQ(content=token)
                else:
                    # possibly a special keyword
                    keyword, rest = token.split(':', 1)
                    keyword = keyword.lower()
                    if keyword == 'category':
                        category = self._get_object(Category, rest,
                                               'name', 'slug', 'pk')
                        if category is None:
                            continue
                        sq = _exact_q(self, 'categories', category.pk)
                    elif keyword == 'feed':
                        feed = self._get_object(Feed, rest,
                                           'name', 'pk')
                        if feed is None:
                            continue
                        sq = _exact_q(self, 'feed', feed.pk)
                    elif keyword == 'search':
                        search = self._get_object(SavedSearch, rest,
                                             'query_string', 'pk')
                        if search is None:
                            continue
                        sq = _exact_q(self, 'search', search.pk)
                    elif keyword == 'tag':
                        tag = self._get_object(Tag, rest, 'name')
                        if tag is None:
                            continue
                        sq = _exact_q(self, 'tags', tag.pk)
                    elif keyword == 'user':
                        user = self._get_object(User, rest,
                                           'username', 'pk')
                        if user is None:
                            continue
                        sq = (_exact_q(self, 'user', user.pk) |
                              _exact_q(self, 'authors', user.pk))
                    elif keyword == 'playlist':
                        playlist = self._get_object(Playlist, rest, 'pk')
                        if playlist is None and '/' in rest:
                            # user/slug
                            user, slug = rest.split('/', 1)
                            try:
                                playlist = Playlist.objects.get(
                                    user__username=user,
                                    slug=slug)
                            except Playlist.DoesNotExist:
                                pass
                        if playlist is None:
                            continue
                        sq = _exact_q(self, 'playlists', playlist.pk)
                    else:
                        sq = SQ(content=token)
                if negated:
                    sq = ~sq
            elif isinstance(token, (list, tuple)):
                # or block
                or_sq_list = filter(None,
                                    (self._tokens_to_sq([or_token])
                                     for or_token in token))
                if not or_sq_list:
                    continue
                sq = reduce(operator.or_, or_sq_list)
            else:
                raise ValueError("Invalid token: {0!r}".format(token))
            sq_list.append(sq)
        if not sq_list:
            return None
        return reduce(operator.and_, sq_list)

    def _filter_for_tokens(self, tokens):
        """
        Takes a list of tokens and returns a copy of the current
        SearchQuerySet filtered for those tokens.

        """
        sq = self._tokens_to_sq(tokens)
        if sq is None:
            return self._clone()
        return self.filter(sq)

    def auto_query(self, query_string):
        """
        Performs a best guess constructing the search query.

        """
        return self._filter_for_tokens(self.tokenize(query_string))
