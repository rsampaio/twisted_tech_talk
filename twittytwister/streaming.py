# -*- test-case-name: twittytwister.test.test_streaming -*-
#
# Copyright (c) 2010-2012 Ralph Meijer <ralphm@ik.nu>
# See LICENSE.txt for details

"""
Twitter Streaming API.

@see: U{http://dev.twitter.com/pages/streaming_api}.
"""

import simplejson as json

from twisted.internet import defer
from twisted.protocols.basic import LineReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.python import log
from twisted.web.client import ResponseDone
from twisted.web.http import PotentialDataLoss

class LengthDelimitedStream(LineReceiver):
    """
    Length-delimited datagram decoder protocol.

    Datagrams are prefixed by a line with a decimal length in ASCII. Lines are
    delimited by C{\r\n} and maybe empty, for keep-alive purposes.
    """

    def __init__(self):
        self._rawBuffer = None
        self._rawBufferLength = None
        self._expectedLength = None


    def lineReceived(self, line):
        """
        Called when a line is received.

        We expect a length in bytes or an empty line for keep-alive. If
        we got a length, switch to raw mode to receive that amount of bytes.
        """
        if line and line.isdigit():
            self._expectedLength = int(line)
            self._rawBuffer = []
            self._rawBufferLength = 0
            self.setRawMode()
        else:
            self.keepAliveReceived()


    def rawDataReceived(self, data):
        """
        Called when raw data is received.

        Fill the raw buffer C{_rawBuffer} until we have received at least
        C{_expectedLength} bytes. Call C{datagramReceived} with the received
        byte string of the expected size. Then switch back to line mode with
        the remainder of the buffer.
        """
        self._rawBuffer.append(data)
        self._rawBufferLength += len(data)

        if self._rawBufferLength >= self._expectedLength:
            receivedData = ''.join(self._rawBuffer)
            expectedData = receivedData[:self._expectedLength]
            extraData = receivedData[self._expectedLength:]

            self._rawBuffer = None
            self._rawBufferLength = None
            self._expectedLength = None

            self.datagramReceived(expectedData)
            self.setLineMode(extraData)


    def datagramReceived(self, data):
        """
        Called when a datagram is received.
        """
        raise NotImplementedError()


    def keepAliveReceived(self):
        """
        Called when a empty line as keep-alive is received.

        This can be overridden for logging purposes.
        """



class TwitterObject(object):
    """
    A Twitter object.
    """
    raw = None
    SIMPLE_PROPS = None
    COMPLEX_PROPS = None
    LIST_PROPS = None

    @classmethod
    def fromDict(cls, data):
        """
        Fill this objects attributes from a dict for known properties.
        """
        obj = cls()
        obj.raw = data
        for name, value in data.iteritems():
            if cls.SIMPLE_PROPS and name in cls.SIMPLE_PROPS:
                setattr(obj, name, value)
            elif cls.COMPLEX_PROPS and name in cls.COMPLEX_PROPS:
                value = cls.COMPLEX_PROPS[name].fromDict(value)
                setattr(obj, name, value)
            elif cls.LIST_PROPS and name in cls.LIST_PROPS:
                value = [cls.LIST_PROPS[name].fromDict(item)
                         for item in value]
                setattr(obj, name, value)

        return obj


    def __repr__(self):
        bodyParts = []
        for name in dir(self):
            if self.SIMPLE_PROPS and name in self.SIMPLE_PROPS:
                if hasattr(self, name):
                    bodyParts.append("%s=%s" % (name,
                                                repr(getattr(self, name))))

            elif self.COMPLEX_PROPS and name in self.COMPLEX_PROPS:
                if hasattr(self, name):
                    bodyParts.append("%s=%s" % (name,
                                                repr(getattr(self, name))))
            elif self.LIST_PROPS and name in self.LIST_PROPS:
                if hasattr(self, name):
                    items = getattr(self, name)

                    itemBodyParts = []
                    for item in items:
                        itemBodyParts.append(repr(item))

                    itemBody = ',\n'.join(itemBodyParts)
                    lines = itemBody.splitlines()
                    itemBody = '\n    '.join(lines)

                    if itemBody:
                        itemBody = '\n    %s\n' % (itemBody,)

                    bodyParts.append("%s=[%s]" % (name, itemBody))

        body = ',\n'.join(bodyParts)
        lines = body.splitlines()
        body = '\n    '.join(lines)

        result = "%s(\n    %s\n)" % (self.__class__.__name__, body)
        return result



class Indices(TwitterObject):
    """
    Indices for tweet entities.
    """
    start = None
    end = None

    @classmethod
    def fromDict(cls, data):
        obj = cls()
        obj.raw = data
        try:
            obj.start, obj.end = data
        except (TypeError, ValueError):
            log.err()
        return obj

    def __repr__(self):
        return "%s(start=%s, end=%s)" % (self.__class__.__name__,
                                         self.start, self.end)



class Size(TwitterObject):
    """
    Size of a media object.
    """
    SIMPLE_PROPS = set(['w', 'h', 'resize'])



class Sizes(TwitterObject):
    """
    Available sizes for a media object.
    """
    COMPLEX_PROPS = {'large': Size,
                     'medium': Size,
                     'small': Size,
                     'thumb': Size}



class Media(TwitterObject):
    """
    Media entity.
    """
    SIMPLE_PROPS = set(['id', 'media_url', 'media_url_https', 'url',
                        'display_url', 'expanded_url', 'type'])
    COMPLEX_PROPS = {'indices': Indices, 'sizes': Sizes}



class URL(TwitterObject):
    """
    URL entity.
    """
    SIMPLE_PROPS = set(['url', 'display_url', 'expanded_url'])
    COMPLEX_PROPS = {'indices': Indices}



class UserMention(TwitterObject):
    SIMPLE_PROPS = set(['id', 'screen_name', 'name'])
    COMPLEX_PROPS = {'indices': Indices}



class HashTag(TwitterObject):
    SIMPLE_PROPS = set(['text'])
    COMPLEX_PROPS = {'indices': Indices}



class Entities(TwitterObject):
    """
    Tweet entities.
    """
    LIST_PROPS = {'media': Media, 'urls': URL,
                  'user_mentions': UserMention, 'hashtags': HashTag}



class Status(TwitterObject):
    """
    Twitter Status.
    """
    SIMPLE_PROPS = set(['created_at', 'id', 'text', 'source', 'truncated',
        'in_reply_to_status_id', 'in_reply_to_screen_name',
        'in_reply_to_user_id', 'favorited', 'user_id', 'geo'])
    COMPLEX_PROPS = {'entities': Entities}

# circular reference:
Status.COMPLEX_PROPS['retweeted_status'] = Status



class User(TwitterObject):
    """
    Twitter User.
    """
    SIMPLE_PROPS = set(['id', 'name', 'screen_name', 'location', 'description',
        'profile_image_url', 'url', 'protected', 'followers_count',
        'profile_background_color', 'profile_text_color', 'profile_link_color',
        'profile_sidebar_fill_color', 'profile_sidebar_border_color',
        'friends_count', 'created_at', 'favourites_count', 'utc_offset',
        'time_zone', 'following', 'notifications', 'statuses_count',
        'profile_background_image_url', 'profile_background_tile', 'verified',
        'geo_enabled'])
    COMPLEX_PROPS = {'status': Status}

# circular reference:
Status.COMPLEX_PROPS['user'] = User



class TwitterStream(LengthDelimitedStream, TimeoutMixin):
    """
    Twitter Stream.

    This protocol decodes an JSON encoded stream of Twitter statuses and
    associated datastructures, where each datagram is length-delimited.

    L{TimeoutMixin} is used to disconnect the stream in case Twitter stops
    sending data, including the keep-alives that usually result in traffic
    at least every 30 seconds. If not passed using C{timeoutPeriod}, the
    timeout period is set to 60 seconds.
    """

    def __init__(self, callback, timeoutPeriod=60):
        LengthDelimitedStream.__init__(self)
        self.setTimeout(timeoutPeriod)
        self.callback = callback
        self.deferred = defer.Deferred()


    def dataReceived(self, data):
        """
        Called when data is received.

        This overrides the default implementation from LineReceiver to
        reset the connection timeout.
        """
        self.resetTimeout()
        LengthDelimitedStream.dataReceived(self, data)


    def datagramReceived(self, data):
        """
        Decode the JSON-encoded datagram and call the callback.
        """
        try:
            obj = json.loads(data)
        except ValueError, e:
            log.err(e, 'Invalid JSON in stream: %r' % data)
            return

        if u'text' in obj:
            obj = Status.fromDict(obj)
        else:
            log.msg('Unsupported object %r' % obj)
            return

        self.callback(obj)


    def connectionLost(self, reason):
        """
        Called when the body is complete or the connection was lost.

        @note: As the body length is usually not known at the beginning of the
        response we expect a L{PotentialDataLoss} when Twitter closes the
        stream, instead of L{ResponseDone}. Other exceptions are treated
        as error conditions.
        """
        self.setTimeout(None)
        if reason.check(ResponseDone, PotentialDataLoss):
            self.deferred.callback(None)
        else:
            self.deferred.errback(reason)


    def timeoutConnection(self):
        """
        Called when the connection times out.

        This protocol is used to process the HTTP response body. Its transport
        is really a proxy, that does not provide C{loseConnection}. Instead it
        has C{stopProducing}, which will result in the real transport being
        closed when called.
        """
        self.transport.stopProducing()
