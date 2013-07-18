#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import cyclone.escape
import cyclone.web
import cyclone.websocket
import os.path
import sys
from oauth import oauth

from twisted.python import log
from twisted.internet import reactor
from twittytwister import twitter

class Application(cyclone.web.Application):
    def __init__(self):
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            template_path=os.path.join(os.path.dirname(__file__), "static"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            autoescape=None,
        )

        handlers = [
            (r"/", MainHandler),
            (r"/tweetbox", TweetSocketHandler),
            (r"/(.*)", cyclone.web.StaticFileHandler,
                dict(path=settings['static_path'])),
        ]
        cyclone.web.Application.__init__(self, handlers, **settings)

class MainHandler(cyclone.web.RequestHandler):
    def get(self):
        self.render("index.html")

class TweetSocketHandler(cyclone.websocket.WebSocketHandler):
    def connectionMade(self, *args, **kwargs):
        log.msg("ws opened")

        # create a auth.py with 2 vars: 
        # consumer(oauth.OAuthConsumer) and token(oauth.OAuthToken)
        auth = __import__("auth")
        twitter.TwitterFeed(
            consumer=auth.consumer, 
            token=auth.token) \
        .track(self.tweetReceived, set(["locaweb", "techtalk"])) \
        .addErrback(log.err)

    def tweetReceived(self, tweet):
        log.msg("tweet received", tweet.text)
        self.sendMessage(tweet.text)

    def connectionLost(self, reason):
        log.msg("ws closed %s" % reason)

    def messageReceived(self, message):
        log.msg("got message %s" % message)
        self.sendMessage(message)


def main():
    reactor.listenTCP(8888, Application())
    reactor.run()


if __name__ == "__main__":
    log.startLogging(sys.stdout)
    main()
