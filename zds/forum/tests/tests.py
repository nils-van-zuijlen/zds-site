# coding: utf-8

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase

from zds.forum.factories import CategoryFactory, ForumFactory, \
    TopicFactory, PostFactory, TagFactory
from zds.forum.models import Forum, TopicRead
from zds.forum.models import Post, Topic
from zds.member.factories import ProfileFactory, StaffProfileFactory
from zds.notification.models import TopicAnswerSubscription
from zds.utils import slugify
from zds.utils.forums import get_tag_by_title
from zds.utils.models import CommentLike, CommentDislike, Alert, Tag
from zds import settings as zds_settings


class ForumMemberTests(TestCase):

    def setUp(self):

        settings.EMAIL_BACKEND = \
            'django.core.mail.backends.locmem.EmailBackend'

        self.category1 = CategoryFactory(position=1)
        self.category2 = CategoryFactory(position=2)
        self.category3 = CategoryFactory(position=3)
        self.forum11 = ForumFactory(
            category=self.category1,
            position_in_category=1)
        self.forum12 = ForumFactory(
            category=self.category1,
            position_in_category=2)
        self.forum13 = ForumFactory(
            category=self.category1,
            position_in_category=3)
        self.forum21 = ForumFactory(
            category=self.category2,
            position_in_category=1)
        self.forum22 = ForumFactory(
            category=self.category2,
            position_in_category=2)
        self.user = ProfileFactory().user
        self.user2 = ProfileFactory().user
        log = self.client.login(
            username=self.user.username,
            password='hostel77')
        self.assertEqual(log, True)

        settings.ZDS_APP['member']['bot_account'] = ProfileFactory().user.username

    def feed_rss_display(self):
        """Test each rss feed feed"""
        response = self.client.get(reverse('post-feed-rss'), follow=False)
        self.assertEqual(response.status_code, 200)

        for forum in Forum.objects.all():
            response = self.client.get(reverse('post-feed-rss') + "?forum={}".format(forum.pk), follow=False)
            self.assertEqual(response.status_code, 200)

        for tag in Tag.objects.all():
            response = self.client.get(reverse('post-feed-rss') + "?tag={}".format(tag.pk), follow=False)
            self.assertEqual(response.status_code, 200)

        for forum in Forum.objects.all():
            for tag in Tag.objects.all():
                response = self.client.get(
                    reverse('post-feed-rss') +
                    "?tag={}&forum={}".format(
                        tag.pk,
                        forum.pk),
                    follow=False)
                self.assertEqual(response.status_code, 200)

    def test_display(self):
        """Test forum display (full: root, category, forum) Topic display test
        is in creation topic test."""
        # Forum root
        response = self.client.get(reverse('cats-forums-list'))
        self.assertContains(response, 'Liste des forums')
        # Category
        response = self.client.get(
            reverse(
                'cat-forums-list',
                args=[
                    self.category1.slug]))
        self.assertContains(response, self.category1.title)
        # Forum
        response = self.client.get(reverse('forum-topics-list', args=[self.category1.slug, self.forum11.slug]))
        self.assertContains(response, self.category1.title)
        self.assertContains(response, self.forum11.title)

    def test_create_topic(self):
        """To test all aspects of topic's creation by member."""
        result = self.client.post(
            reverse('topic-new') + '?forum={0}'
            .format(self.forum12.pk),
            {'title': u'Un autre sujet',
             'subtitle': u'Encore ces lombards en plein ete',
             'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
             },
            follow=False)
        self.assertEqual(result.status_code, 302)

        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 1)
        topic = Topic.objects.first()
        # check post's number
        self.assertEqual(Post.objects.all().count(), 1)
        post = Post.objects.first()

        # check topic and post
        self.assertEqual(post.topic, topic)

        # check position
        self.assertEqual(post.position, 1)

        self.assertEqual(post.author, self.user)
        self.assertEqual(post.editor, None)
        self.assertNotEqual(post.ip_address, None)
        self.assertNotEqual(post.text_html, None)
        self.assertEqual(post.like, 0)
        self.assertEqual(post.dislike, 0)
        self.assertEqual(post.is_visible, True)

        # check last message
        self.assertEqual(topic.last_message, post)

        # Check view
        response = self.client.get(topic.get_absolute_url())
        self.assertContains(response, self.category1.title)
        self.assertContains(response, self.forum11.title)
        self.assertContains(response, topic.title)
        self.assertContains(response, topic.subtitle)

    def test_create_topic_failing_param(self):
        """Testing different failing cases"""

        # With a weird pk
        result = self.client.post(
            reverse('topic-new') + '?forum=' + 'abc',
            {'title': u'Un autre sujet',
             'subtitle': u'Encore ces lombards en plein ete',
             'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
             },
            follow=False)
        self.assertEqual(result.status_code, 404)

        # With a missing pk
        result = self.client.post(
            reverse('topic-new') + '?forum=',
            {'title': u'Un autre sujet',
             'subtitle': u'Encore ces lombards en plein ete',
             'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
             },
            follow=False)
        self.assertEqual(result.status_code, 404)

        # With a missing parameter
        result = self.client.post(
            reverse('topic-new'),
            {'title': u'Un autre sujet',
             'subtitle': u'Encore ces lombards en plein ete',
             'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
             },
            follow=False)
        self.assertEqual(result.status_code, 404)

    def test_answer(self):
        """To test all aspects of answer."""
        user1 = ProfileFactory().user
        user2 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=self.user, position=2)
        post3 = PostFactory(topic=topic1, author=user1, position=3)
        TopicRead(topic=topic1, user=user1, post=post3).save()
        TopicRead(topic=topic1, user=user2, post=post3).save()
        TopicRead(topic=topic1, user=self.user, post=post3).save()
        TopicAnswerSubscription.objects.toggle_follow(topic1, user1, True)
        TopicAnswerSubscription.objects.toggle_follow(topic1, user2, True)
        TopicAnswerSubscription.objects.toggle_follow(topic1, self.user, True)

        # check if we send ane empty text
        result = self.client.post(
            reverse('post-new') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u''
            },
            follow=False)
        self.assertEqual(result.status_code, 200)
        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 1)
        # check post's number (should be 3 for the moment)
        self.assertEqual(Post.objects.all().count(), 3)

        # now check what happen if everything is fine
        result = self.client.post(
            reverse('post-new') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEquals(len(mail.outbox), 2)

        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 1)

        # check post's number
        self.assertEqual(Post.objects.all().count(), 4)

        # check topic and post
        self.assertEqual(post1.topic, topic1)
        self.assertEqual(post2.topic, topic1)
        self.assertEqual(post3.topic, topic1)

        # check values
        post_final = Post.objects.last()
        self.assertEqual(post_final.topic, topic1)
        self.assertEqual(post_final.position, 4)
        self.assertEqual(post_final.editor, None)
        self.assertEqual(
            post_final.text,
            u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter ')

        # test antispam return 403
        result = self.client.post(
            reverse('post-new') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u'Testons l\'antispam'
            },
            follow=False)
        self.assertEqual(result.status_code, 403)

    def test_failing_answer_cases(self):
        """To test some failing aspects of answer."""
        user1 = ProfileFactory().user
        user2 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post3 = PostFactory(topic=topic1, author=user1, position=3)
        TopicRead(topic=topic1, user=user1, post=post3).save()
        TopicRead(topic=topic1, user=user2, post=post3).save()
        TopicRead(topic=topic1, user=self.user, post=post3).save()
        TopicAnswerSubscription.objects.toggle_follow(topic1, user1, True)
        TopicAnswerSubscription.objects.toggle_follow(topic1, user2, True)
        TopicAnswerSubscription.objects.toggle_follow(topic1, self.user, True)

        # missing parameter
        result = self.client.post(
            reverse('post-new'),
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 404)

        # weird parameter
        result = self.client.post(
            reverse('post-new') + '?sujet=' + 'abc',
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 404)

        # non-existing (yet) parameter
        result = self.client.post(
            reverse('post-new') + '?sujet=' + '424242',
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 404)

    def test_edit_main_post(self):
        """To test all aspects of the edition of main post by member."""
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        topic2 = TopicFactory(forum=self.forum12, author=self.user)
        post2 = PostFactory(topic=topic2, author=self.user, position=1)
        topic3 = TopicFactory(forum=self.forum21, author=self.user)
        post3 = PostFactory(topic=topic3, author=self.user, position=1)

        expected_title = u'Un autre sujet'
        expected_subtitle = u'Encore ces lombards en plein été'
        expected_text = u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
        result = self.client.post(
            reverse('topic-edit') + '?topic={0}'.format(topic1.pk),
            {
                'title': expected_title,
                'subtitle': expected_subtitle,
                'text': expected_text
            },
            follow=False)

        self.assertEqual(result.status_code, 302)

        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 3)

        # check post's number
        self.assertEqual(Post.objects.all().count(), 3)

        # check topic and post
        self.assertEqual(post1.topic, topic1)
        self.assertEqual(post2.topic, topic2)
        self.assertEqual(post3.topic, topic3)

        # check values
        self.assertEqual(expected_title, Topic.objects.get(pk=topic1.pk).title)
        self.assertEqual(expected_subtitle, Topic.objects.get(pk=topic1.pk).subtitle)
        self.assertEqual(expected_text, Post.objects.get(pk=post1.pk).text)

        # check edit data
        self.assertEqual(Post.objects.get(pk=post1.pk).editor, self.user)

        # check if topic is valid (no topic)
        result = self.client.post(
            reverse('topic-edit') + '?topic={0}'.format(topic2.pk),
            {
                'title': '',
                'subtitle': expected_subtitle,
                'text': expected_text
            },
            follow=False)
        self.assertEqual(Topic.objects.get(pk=topic2.pk).title, topic2.title)

        # check if topic is valid (tags only)
        result = self.client.post(
            reverse('topic-edit') + '?topic={0}'.format(topic2.pk),
            {
                'title': u'[foo][bar]',
                'subtitle': expected_subtitle,
                'text': expected_text
            },
            follow=False)
        self.assertEqual(Topic.objects.get(pk=topic2.pk).title, topic2.title)

        # check if topic is valid (spaces only)
        result = self.client.post(
            reverse('topic-edit') + '?topic={0}'.format(topic2.pk),
            {
                'title': u'  ',
                'subtitle': expected_subtitle,
                'text': expected_text
            },
            follow=False)
        self.assertEqual(Topic.objects.get(pk=topic2.pk).title, topic2.title)

        # check if topic is valid (valid title)
        result = self.client.post(
            reverse('topic-edit') + '?topic={0}'.format(topic2.pk),
            {
                'title': expected_title,
                'subtitle': expected_subtitle,
                'text': expected_text
            },
            follow=False)
        self.assertEqual(expected_title, Topic.objects.get(pk=topic2.pk).title)

    def test_edit_post(self):
        """To test all aspects of the edition of simple post by member."""
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=self.user, position=2)
        post3 = PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post2.pk),
            {
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)

        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 1)

        # check post's number
        self.assertEqual(Post.objects.all().count(), 3)

        # check topic and post
        self.assertEqual(post1.topic, topic1)
        self.assertEqual(post2.topic, topic1)
        self.assertEqual(post3.topic, topic1)

        # check values
        self.assertEqual(
            Post.objects.get(
                pk=post2.pk).text,
            u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter ')

        # check edit data
        self.assertEqual(Post.objects.get(pk=post2.pk).editor, self.user)

        # if the post pk is altered
        result = self.client.post(
            reverse('post-edit') + '?message=abcd',
            {
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 404)

    def test_edit_post_with_blank(self):

        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=self.user, position=2)
        post3 = PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post2.pk),
            {
                'text': u"  "
            },
            follow=True)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.request["PATH_INFO"], "/forums/message/editer/")
        self.assertEqual(result.request["QUERY_STRING"], "message={}".format(post2.pk))

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post3.pk),
            {
                'text': u" contenu "
            },
            follow=True)

        self.assertEqual(result.status_code, 200)
        self.assertNotEqual(result.request["PATH_INFO"], "/forums/message/editer/")

    def test_quote_post(self):
        """To test when a member quote anyone post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.get(reverse('post-new') + '?sujet={0}&cite={1}'.format(topic1.pk, post2.pk), follow=True)

        self.assertEqual(result.status_code, 200)

        # if the quote pk is altered
        result = self.client.get(reverse('post-new') + '?sujet={0}&cite=abcd'.format(topic1.pk), follow=True)

        self.assertEqual(result.status_code, 404)

    def test_signal_post(self):
        """To test when a member signal a post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post2.pk),
            {
                'signal_text': u'Troll',
                'signal_message': 'confirmer'
            },
            follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(Alert.objects.all().count(), 1)
        self.assertEqual(Alert.objects.filter(author=self.user).count(), 1)
        self.assertEqual(Alert.objects.get(author=self.user).text, u'Troll')

        # and test that staff can solve but not user
        alert = Alert.objects.get(comment=post2.pk)
        # try as a normal user
        result = self.client.post(
            reverse('forum-solve-alert'),
            {
                'alert_pk': alert.pk,
            },
            follow=False)
        self.assertEqual(result.status_code, 403)
        # login as staff
        staff1 = StaffProfileFactory().user
        self.assertEqual(
            self.client.login(
                username=staff1.username,
                password='hostel77'),
            True)
        # try again as staff
        result = self.client.post(
            reverse('forum-solve-alert'),
            {
                'alert_pk': alert.pk,
                'text': u'Everything is Ok kid'
            },
            follow=False)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(Alert.objects.all().count(), 0)

    def test_signal_and_solve_alert_empty_message(self):
        """To test when a member signal a post and staff solve it."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post2.pk),
            {
                'signal_text': u'Troll',
                'signal_message': 'confirmer'
            },
            follow=False)

        alert = Alert.objects.get(comment=post2.pk)
        # login as staff
        staff1 = StaffProfileFactory().user
        self.assertEqual(
            self.client.login(
                username=staff1.username,
                password='hostel77'),
            True)
        # try again as staff
        result = self.client.post(
            reverse('forum-solve-alert'),
            {
                'alert_pk': alert.pk,
            },
            follow=False)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(Alert.objects.all().count(), 0)

    def test_like_post(self):
        """Test when a member like any post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        post3 = PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.post(reverse('post-like') + '?message={0}'.format(post2.pk), follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(CommentLike.objects.all().count(), 1)
        self.assertEqual(Post.objects.get(pk=post1.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).like, 1)
        self.assertEqual(Post.objects.get(pk=post3.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).dislike, 0)
        self.assertEqual(
            CommentLike.objects.filter(
                comments__pk=post1.pk).all().count(),
            0)
        self.assertEqual(
            CommentLike.objects.filter(
                comments__pk=post2.pk).all().count(),
            1)
        self.assertEqual(
            CommentLike.objects.filter(
                comments__pk=post3.pk).all().count(),
            0)

        result = self.client.post(reverse('post-like') + '?message={0}'.format(post1.pk), follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(CommentLike.objects.all().count(), 1)
        self.assertEqual(Post.objects.get(pk=post1.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).like, 1)
        self.assertEqual(Post.objects.get(pk=post3.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).dislike, 0)
        self.assertEqual(
            CommentLike.objects.filter(
                comments__pk=post1.pk).all().count(),
            0)
        self.assertEqual(
            CommentLike.objects.filter(
                comments__pk=post2.pk).all().count(),
            1)
        self.assertEqual(
            CommentLike.objects.filter(
                comments__pk=post3.pk).all().count(),
            0)

    def test_failing_like_post(self):
        """Test failing cases when a member like any post."""

        # parameter is missing
        result = self.client.post(reverse('post-like'), follow=False)

        self.assertEqual(result.status_code, 404)

        # parameter is weird
        result = self.client.post(reverse('post-like') + '?message=' + 'abc', follow=False)

        self.assertEqual(result.status_code, 404)

        # pk doesn't (yet) exist
        result = self.client.post(reverse('post-like') + '?message=' + '424242', follow=False)

        self.assertEqual(result.status_code, 404)

    def test_dislike_post(self):
        """Test when a member dislike any post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        post3 = PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.post(reverse('post-dislike') + '?message={0}'.format(post2.pk), follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(CommentDislike.objects.all().count(), 1)
        self.assertEqual(Post.objects.get(pk=post1.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).dislike, 1)
        self.assertEqual(Post.objects.get(pk=post3.pk).dislike, 0)
        self.assertEqual(
            CommentDislike.objects.filter(
                comments__pk=post1.pk).all().count(),
            0)
        self.assertEqual(
            CommentDislike.objects.filter(
                comments__pk=post2.pk).all().count(),
            1)
        self.assertEqual(
            CommentDislike.objects.filter(
                comments__pk=post3.pk).all().count(),
            0)

        result = self.client.post(reverse('post-like') + '?message={0}'.format(post1.pk), follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(CommentDislike.objects.all().count(), 1)
        self.assertEqual(Post.objects.get(pk=post1.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).dislike, 1)
        self.assertEqual(Post.objects.get(pk=post3.pk).dislike, 0)
        self.assertEqual(
            CommentDislike.objects.filter(
                comments__pk=post1.pk).all().count(),
            0)
        self.assertEqual(
            CommentDislike.objects.filter(
                comments__pk=post2.pk).all().count(),
            1)
        self.assertEqual(
            CommentDislike.objects.filter(
                comments__pk=post3.pk).all().count(),
            0)

    def test_failing_dislike_post(self):
        """Test failing cases when a member dislike any post."""

        # parameter is missing
        result = self.client.post(reverse('post-dislike'), follow=False)

        self.assertEqual(result.status_code, 404)

        # parameter is weird
        result = self.client.post(reverse('post-dislike') + '?message=' + 'abc', follow=False)

        self.assertEqual(result.status_code, 404)

        # pk doesn't (yet) exist
        result = self.client.post(reverse('post-dislike') + '?message=' + '424242', follow=False)

        self.assertEqual(result.status_code, 404)

    def test_useful_post(self):
        """To test when a member mark a post is usefull."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        post3 = PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.post(reverse('post-useful') + '?message={0}'.format(post2.pk), follow=False)

        self.assertEqual(result.status_code, 302)

        self.assertEqual(Post.objects.get(pk=post1.pk).is_useful, False)
        self.assertEqual(Post.objects.get(pk=post2.pk).is_useful, True)
        self.assertEqual(Post.objects.get(pk=post3.pk).is_useful, False)

        # useful the first post
        result = self.client.post(reverse('post-useful') + '?message={0}'.format(post1.pk), follow=False)
        self.assertEqual(result.status_code, 403)

        self.assertEqual(Post.objects.get(pk=post1.pk).is_useful, False)
        self.assertEqual(Post.objects.get(pk=post2.pk).is_useful, True)
        self.assertEqual(Post.objects.get(pk=post3.pk).is_useful, False)

        # useful if you aren't author
        TopicFactory(forum=self.forum11, author=user1)
        post4 = PostFactory(topic=topic1, author=user1, position=1)
        post5 = PostFactory(topic=topic1, author=self.user, position=2)

        result = self.client.post(reverse('post-useful') + '?message={0}'.format(post5.pk), follow=False)

        self.assertEqual(result.status_code, 403)

        self.assertEqual(Post.objects.get(pk=post4.pk).is_useful, False)
        self.assertEqual(Post.objects.get(pk=post5.pk).is_useful, False)

        # useful if you are staff
        StaffProfileFactory().user
        self.assertEqual(self.client.login(
            username=self.user.username,
            password='hostel77'),
            True)
        result = self.client.post(reverse('post-useful') + '?message={0}'.format(post4.pk), follow=False)
        self.assertNotEqual(result.status_code, 403)
        self.assertEqual(Post.objects.get(pk=post4.pk).is_useful, True)
        self.assertEqual(Post.objects.get(pk=post5.pk).is_useful, False)

    def test_failing_useful_post(self):
        """To test some failing cases when a member mark a post is useful."""

        # missing parameter
        result = self.client.post(reverse('post-useful'), follow=False)

        self.assertEqual(result.status_code, 404)

        # weird parameter
        result = self.client.post(reverse('post-useful') + '?message=' + 'abc', follow=False)

        self.assertEqual(result.status_code, 404)

        # not existing (yet) pk parameter
        result = self.client.post(reverse('post-useful') + '?message=' + '424242', follow=False)

        self.assertEqual(result.status_code, 404)

    def test_move_topic(self):
        """Test topic move."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        # not staff member can't move topic
        result = self.client.post(
            reverse('topic-edit'),
            {
                'move': '',
                'forum': self.forum12,
                'topic': topic1.pk
            }, follow=False)

        self.assertEqual(result.status_code, 403)

        # test with staff
        staff1 = StaffProfileFactory().user
        self.assertEqual(
            self.client.login(
                username=staff1.username,
                password='hostel77'),
            True)

        result = self.client.post(
            reverse('topic-edit'),
            {
                'move': '',
                'forum': self.forum12.pk,
                'topic': topic1.pk
            }, follow=False)

        self.assertEqual(result.status_code, 302)

        # check value
        self.assertEqual(
            Topic.objects.get(
                pk=topic1.pk).forum.pk,
            self.forum12.pk)

    def test_failing_moving_topic(self):
        """Test some failing case when playing with the "move topic" feature"""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        # log as staff
        staff1 = StaffProfileFactory().user
        self.assertEqual(
            self.client.login(
                username=staff1.username,
                password='hostel77'),
            True)

        # missing parameter
        result = self.client.post(
            reverse('topic-edit'),
            {
                'move': '',
                'forum': self.forum12.pk,
            }, follow=False)

        self.assertEqual(result.status_code, 404)

        # weird parameter
        result = self.client.post(
            reverse('topic-edit'),
            {
                'move': '',
                'forum': self.forum12.pk,
                'topic': 'abc'
            }, follow=False)

        self.assertEqual(result.status_code, 404)

        # non-existing (yet) parameter
        result = self.client.post(
            reverse('topic-edit'),
            {
                'move': '',
                'forum': self.forum12.pk,
                'topic': '424242'
            }, follow=False)

        self.assertEqual(result.status_code, 404)

    def test_answer_empty(self):
        """Test behaviour on empty answer."""
        # Topic and 1st post by another user, to avoid antispam limitation
        topic1 = TopicFactory(forum=self.forum11, author=self.user2)
        PostFactory(topic=topic1, author=self.user2, position=1)

        result = self.client.post(
            reverse('post-new') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u' '
            },
            follow=False)

        # Empty text --> preview = HTTP 200 + post not saved (only 1 post in
        # topic)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(Post.objects.filter(topic=topic1.pk).count(), 1)

    def test_add_tag(self):

        tag_c_sharp = TagFactory(title="C#")

        tag_c = TagFactory(title="C")
        self.assertEqual(tag_c_sharp.slug, tag_c.slug)
        self.assertNotEqual(tag_c_sharp.title, tag_c.title)
        # post a topic with a tag
        result = self.client.post(
            reverse('topic-new') + '?forum={0}'
            .format(self.forum12.pk),
            {'title': u'[C#]Un autre sujet',
             'subtitle': u'Encore ces lombards en plein ete',
             'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
             },
            follow=False)
        self.assertEqual(result.status_code, 302)

        # test the topic is added to the good tag

        self.assertEqual(Topic.objects.filter(
            tags__in=[tag_c_sharp])
            .order_by("-last_message__pubdate").prefetch_related(
            "tags").count(), 1)
        self.assertEqual(Topic.objects.filter(tags__in=[tag_c])
                         .order_by("-last_message__pubdate").prefetch_related(
            "tags").count(), 0)
        topic_with_conflict_tags = TopicFactory(
            forum=self.forum11, author=self.user)
        topic_with_conflict_tags.title = u"[C][c][ c][C ]name"
        (tags, title) = get_tag_by_title(topic_with_conflict_tags.title)
        topic_with_conflict_tags.add_tags(tags)
        self.assertEqual(topic_with_conflict_tags.tags.all().count(), 1)
        topic_with_conflict_tags = TopicFactory(
            forum=self.forum11, author=self.user)
        topic_with_conflict_tags.title = u"[][ ][   ]name"
        (tags, title) = get_tag_by_title(topic_with_conflict_tags.title)
        topic_with_conflict_tags.add_tags(tags)
        self.assertEqual(topic_with_conflict_tags.tags.all().count(), 0)

    def test_mandatory_fields_on_new(self):
        """Test handeling of mandatory fields on new topic creation."""
        init_topic_count = Topic.objects.all().count()

        # Empty fields
        response = self.client.post(
            reverse('topic-new') +
            '?forum={0}'.format(
                self.forum12.pk),
            {},
            follow=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Topic.objects.all().count(), init_topic_count)

        # Blank data
        response = self.client.post(
            reverse('topic-new') +
            '?forum={0}'.format(
                self.forum12.pk),
            {
                'title': u' ',
                'text': u' ',
            },
            follow=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Topic.objects.all().count(), init_topic_count)

    def test_url_topic(self):
        """Test simple get request to the topic."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        # simple member can read public topic
        result = self.client.get(reverse('topic-posts-list', args=[topic1.pk, slugify(topic1.title)]), follow=True)
        self.assertEqual(result.status_code, 200)

    def test_failing_unread_post(self):
        """Test failing cases when a member try to mark as unread a post."""

        # parameter is missing
        result = self.client.get(reverse('post-unread'), follow=False)

        self.assertEqual(result.status_code, 404)

        # parameter is weird
        result = self.client.get(reverse('post-unread') + '?message=' + 'abc', follow=False)

        self.assertEqual(result.status_code, 404)

        # pk doesn't (yet) exist
        result = self.client.get(reverse('post-unread') + '?message=' + '424242', follow=False)

        self.assertEqual(result.status_code, 404)

    def test_frontend_alert_existence_other_pages(self):
        forum = self.forum11
        profiles = [ProfileFactory(), ProfileFactory()]
        topic = TopicFactory(forum=forum, author=profiles[1].user)
        expected = u"<strong>Attention</strong>, vous n'êtes pas sur la dernière page de "
        expected += u"ce sujet, assurez-vous de l'avoir lu dans son intégralité avant d'y"
        expected += u" répondre."

        for i in range(zds_settings.ZDS_APP['forum']['posts_per_page'] + 2):
            PostFactory(topic=topic, author=profiles[i % 2].user, position=i + 2)
        self.client.login(username=profiles[1].user.username, password="hostel77")

        templateResponse = self.client.get(topic.get_absolute_url())
        self.assertIn(expected, templateResponse.content.decode('utf-8'))

        templateResponse = self.client.get(topic.get_absolute_url() + "?page=2")
        self.assertNotIn(expected, templateResponse.content.decode('utf-8'))


class ForumGuestTests(TestCase):

    def setUp(self):

        settings.EMAIL_BACKEND = \
            'django.core.mail.backends.locmem.EmailBackend'

        self.category1 = CategoryFactory(position=1)
        self.category2 = CategoryFactory(position=2)
        self.category3 = CategoryFactory(position=3)
        self.forum11 = ForumFactory(
            category=self.category1,
            position_in_category=1)
        self.forum12 = ForumFactory(
            category=self.category1,
            position_in_category=2)
        self.forum13 = ForumFactory(
            category=self.category1,
            position_in_category=3)
        self.forum21 = ForumFactory(
            category=self.category2,
            position_in_category=1)
        self.forum22 = ForumFactory(
            category=self.category2,
            position_in_category=2)
        self.user = ProfileFactory().user

    def feed_rss_display(self):
        """Test each rss feed feed"""
        response = self.client.get(reverse('post-feed-rss'), follow=False)
        self.assertEqual(response.status_code, 200)

        for forum in Forum.objects.all():
            response = self.client.get(reverse('post-feed-rss') + "?forum={}".format(forum.pk), follow=False)
            self.assertEqual(response.status_code, 200)

        for tag in Tag.objects.all():
            response = self.client.get(reverse('post-feed-rss') + "?tag={}".format(tag.pk), follow=False)
            self.assertEqual(response.status_code, 200)

        for forum in Forum.objects.all():
            for tag in Tag.objects.all():
                response = self.client.get(
                    reverse('post-feed-rss') +
                    "?tag={}&forum={}".format(
                        tag.pk,
                        forum.pk),
                    follow=False)
                self.assertEqual(response.status_code, 200)

    def test_display(self):
        """Test forum display (full: root, category, forum) Topic display test
        is in creation topic test."""
        # Forum root
        response = self.client.get(reverse('cats-forums-list'))
        self.assertContains(response, 'Liste des forums')
        # Category
        response = self.client.get(
            reverse(
                'cat-forums-list',
                args=[
                    self.category1.slug]))
        self.assertContains(response, self.category1.title)
        # Forum
        response = self.client.get(reverse('forum-topics-list', args=[self.category1.slug, self.forum11.slug]))
        self.assertContains(response, self.category1.title)
        self.assertContains(response, self.forum11.title)

    def test_create_topic(self):
        """To test all aspects of topic's creation by guest."""
        result = self.client.post(
            reverse('topic-new') + '?forum={0}'
            .format(self.forum12.pk),
            {'title': u'Un autre sujet',
             'subtitle': u'Encore ces lombards en plein ete',
             'text': u'C\'est tout simplement l\'histoire de '
             u'la ville de Paris que je voudrais vous conter '
             },
            follow=False)
        self.assertEqual(result.status_code, 302)

        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 0)
        # check post's number
        self.assertEqual(Post.objects.all().count(), 0)

    def test_answer(self):
        """To test all aspects of answer."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=self.user, position=2)
        PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.post(
            reverse('post-new') + '?sujet={0}'.format(topic1.pk),
            {
                'last_post': topic1.last_message.pk,
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)

        # check topic's number
        self.assertEqual(Topic.objects.all().count(), 1)

        # check post's number
        self.assertEqual(Post.objects.all().count(), 3)

    def test_tag_parsing(self):
        """test the tag parsing in nominal, limit and borns cases"""
        (tags, title) = get_tag_by_title("[tag]title")
        self.assertEqual(len(tags), 1)
        self.assertEqual(title, "title")

        (tags, title) = get_tag_by_title("[[tag1][tag2]]title")
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0], "[tag1][tag2]")
        self.assertEqual(title, "title")

        (tags, title) = get_tag_by_title("[tag1][tag2]title")
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], "tag1")
        self.assertEqual(title, "title")
        (tags, title) = get_tag_by_title("[tag1] [tag2]title")
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], "tag1")
        self.assertEqual(title, "title")

        (tags, title) = get_tag_by_title("[tag1][tag2]title[tag3]")
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0], "tag1")
        self.assertEqual(title, "title[tag3]")

        (tags, title) = get_tag_by_title("[tag1[][tag2]title")
        self.assertEqual(len(tags), 0)
        self.assertEqual(title, "[tag1[][tag2]title")

    def test_edit_main_post(self):
        """To test all aspects of the edition of main post by guest."""
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        topic2 = TopicFactory(forum=self.forum12, author=self.user)
        PostFactory(topic=topic2, author=self.user, position=1)
        topic3 = TopicFactory(forum=self.forum21, author=self.user)
        PostFactory(topic=topic3, author=self.user, position=1)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post1.pk),
            {
                'title': u'Un autre sujet',
                'subtitle': u'Encore ces lombards en plein été',
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)

        self.assertNotEqual(
            Topic.objects.get(
                pk=topic1.pk).title,
            u'Un autre sujet')
        self.assertNotEqual(
            Topic.objects.get(
                pk=topic1.pk).subtitle,
            u'Encore ces lombards en plein été')
        self.assertNotEqual(
            Post.objects.get(
                pk=post1.pk).text,
            u'C\'est tout simplement l\'histoire de la ville de '
            u'Paris que je voudrais vous conter ')

    def test_edit_post(self):
        """To test all aspects of the edition of simple post by guest."""
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=self.user, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post2.pk),
            {
                'text': u'C\'est tout simplement l\'histoire de la ville de Paris que je voudrais vous conter '
            },
            follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertNotEqual(
            Post.objects.get(
                pk=post2.pk).text,
            u'C\'est tout simplement l\'histoire de la ville de '
            u'Paris que je voudrais vous conter ')

    def test_quote_post(self):
        """To test when a member quote anyone post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.get(reverse('post-new') + '?sujet={0}&cite={0}'.format(topic1.pk, post2.pk), follow=False)

        self.assertEqual(result.status_code, 302)

    def test_signal_post(self):
        """To test when a member quote anyone post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.post(
            reverse('post-edit') + '?message={0}'.format(post2.pk),
            {
                'signal_text': u'Troll',
                'signal_message': 'confirmer'
            },
            follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertEqual(Alert.objects.all().count(), 0)
        self.assertEqual(Alert.objects.filter(author=self.user).count(), 0)

    def test_like_post(self):
        """Test when a member like any post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        post3 = PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.get(reverse('post-like') + '?message={0}'.format(post2.pk), follow=False)

        self.assertEqual(result.status_code, 405)
        self.assertEqual(CommentLike.objects.all().count(), 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).dislike, 0)

    def test_dislike_post(self):
        """Test when a member dislike any post."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        post3 = PostFactory(topic=topic1, author=self.user, position=3)

        result = self.client.get(reverse('post-dislike') + '?message={0}'.format(post2.pk), follow=False)

        self.assertEqual(result.status_code, 405)
        self.assertEqual(CommentDislike.objects.all().count(), 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).like, 0)
        self.assertEqual(Post.objects.get(pk=post1.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post2.pk).dislike, 0)
        self.assertEqual(Post.objects.get(pk=post3.pk).dislike, 0)

    def test_useful_post(self):
        """To test when a guest mark a post is usefull."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        post1 = PostFactory(topic=topic1, author=self.user, position=1)
        post2 = PostFactory(topic=topic1, author=user1, position=2)
        post3 = PostFactory(topic=topic1, author=user1, position=3)

        result = self.client.get(reverse('post-useful') + '?message={0}'.format(post2.pk), follow=False)

        self.assertEqual(result.status_code, 405)

        self.assertEqual(Post.objects.get(pk=post1.pk).is_useful, False)
        self.assertEqual(Post.objects.get(pk=post2.pk).is_useful, False)
        self.assertEqual(Post.objects.get(pk=post3.pk).is_useful, False)

    def test_move_topic(self):
        """Test topic move."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        # not staff guest can't move topic
        result = self.client.post(
            reverse('topic-edit'),
            {
                'move': '',
                'forum': self.forum12,
                'topic': topic1.pk
            }, follow=False)

        self.assertEqual(result.status_code, 302)
        self.assertNotEqual(Topic.objects.get(pk=topic1.pk).forum, self.forum12)

    def test_url_topic(self):
        """Test simple get request to the topic."""
        user1 = ProfileFactory().user
        topic1 = TopicFactory(forum=self.forum11, author=self.user)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        # guest can read public topic
        result = self.client.get(
            reverse('topic-posts-list', args=[topic1.pk, slugify(topic1.title)]), follow=True)
        self.assertEqual(result.status_code, 200)

    def test_filter_topic(self):
        """Test filters for topics"""

        ProfileFactory().user

        topic = TopicFactory(forum=self.forum11, author=self.user, is_solved=False, is_sticky=False)
        PostFactory(topic=topic, author=self.user, position=1)

        topic_solved = TopicFactory(forum=self.forum11, author=self.user, is_solved=True, is_sticky=False)
        PostFactory(topic=topic_solved, author=self.user, position=1)

        topic_sticky = TopicFactory(forum=self.forum11, author=self.user, is_solved=False, is_sticky=True)
        PostFactory(topic=topic_sticky, author=self.user, position=1)

        topic_solved_sticky = TopicFactory(forum=self.forum11, author=self.user, is_solved=True, is_sticky=True)
        PostFactory(topic=topic_solved_sticky, author=self.user, position=1)

        # no filter

        # all normal (== not sticky) topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=False)), 2)
        self.assertIn(topic_solved, get_topics(forum_pk=self.forum11.pk, is_sticky=False))
        self.assertIn(topic, get_topics(forum_pk=self.forum11.pk, is_sticky=False))

        # all sticky topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=True)), 2)
        self.assertIn(topic_solved_sticky, get_topics(forum_pk=self.forum11.pk, is_sticky=True))

        # solved filter

        # solved topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=False, filter='solve')), 1)
        self.assertEqual(get_topics(forum_pk=self.forum11.pk, is_sticky=False, filter='solve')[0], topic_solved)

        # solved sticky topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=True, filter='solve')), 1)
        self.assertEqual(get_topics(forum_pk=self.forum11.pk, is_sticky=True, filter='solve')[0], topic_solved_sticky)

        # unsolved filter

        # unsolved topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=False, filter='unsolve')), 1)
        self.assertEqual(get_topics(forum_pk=self.forum11.pk, is_sticky=False, filter='unsolve')[0], topic)

        # unsolved sticky topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=True, filter='unsolve')), 1)
        self.assertEqual(get_topics(forum_pk=self.forum11.pk, is_sticky=True, filter='unsolve')[0], topic_sticky)

        # no answer filter

        user1 = ProfileFactory().user

        # create a new topic with answers
        topic1 = TopicFactory(forum=self.forum11, author=self.user, is_solved=False, is_sticky=False)
        PostFactory(topic=topic1, author=self.user, position=1)
        PostFactory(topic=topic1, author=user1, position=2)
        PostFactory(topic=topic1, author=self.user, position=3)

        # create a new sticky topic with answers
        topic2 = TopicFactory(forum=self.forum11, author=self.user, is_solved=False, is_sticky=True)
        PostFactory(topic=topic2, author=self.user, position=1)
        PostFactory(topic=topic2, author=user1, position=2)
        PostFactory(topic=topic2, author=self.user, position=3)

        # all normal (== not sticky) topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=False)), 3)  # 2 normal + 1 with answers
        self.assertIn(topic1, get_topics(forum_pk=self.forum11.pk, is_sticky=False))

        # all sticky topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=True)), 3)  # 2 normal + 1 with answers
        self.assertIn(topic2, get_topics(forum_pk=self.forum11.pk, is_sticky=True))

        # no answer topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=False, filter='noanswer')), 2)
        self.assertIn(topic_solved, get_topics(forum_pk=self.forum11.pk, is_sticky=False, filter='noanswer'))

        # no answer sticky topics
        self.assertEqual(len(get_topics(forum_pk=self.forum11.pk, is_sticky=True, filter='noanswer')), 2)
        self.assertIn(
            topic_solved_sticky,
            get_topics(forum_pk=self.forum11.pk, is_sticky=True, filter='noanswer'),
        )

    def test_old_post_limit(self):
        topic = TopicFactory(forum=self.forum11, author=self.user, is_solved=False, is_sticky=False)

        # Create a post published just now
        PostFactory(topic=topic, author=self.user, position=1)
        self.assertEqual(topic.old_post_warning(), False)

        # Create a post published one day before old_post_limit_days
        old_post = PostFactory(topic=topic, author=self.user, position=2)
        old_post.pubdate = datetime.now() - timedelta(days=(settings.ZDS_APP['forum']['old_post_limit_days'] + 1))
        old_post.save()
        self.assertEqual(topic.old_post_warning(), True)


def get_topics(forum_pk, is_sticky, filter=None):
    """
    Get topics for a forum.
    The optional filter allows to retrieve only solved, unsolved or "non-answered" (i.e. with only the 1st post) topics.
    :param forum_pk: the primary key of forum
    :param is_sticky: indicates if the sticky topics must or must not be retrieved
    :param filter: optional filter to retrieve only specific topics.
    :return:
    """

    if filter == 'solve':
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky, is_solved=True)
    elif filter == 'unsolve':
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky, is_solved=False)
    elif filter == 'noanswer':
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky, last_message__position=1)
    else:
        topics = Topic.objects.filter(forum__pk=forum_pk, is_sticky=is_sticky)

    return topics.order_by('-last_message__pubdate')\
        .select_related('author__profile')\
        .prefetch_related('last_message', 'tags')\
        .all()


class ManagerTests(TestCase):

        def setUp(self):

            self.cat1 = CategoryFactory()
            self.forum1 = ForumFactory(category=self.cat1)
            self.forum2 = ForumFactory(category=self.cat1)

            self.staff = StaffProfileFactory()
            staff_group = Group.objects.filter(name="staff").first()

            self.forum3 = ForumFactory(category=self.cat1)
            self.forum3.group = [staff_group]
            self.forum3.save()

            TopicFactory(forum=self.forum1, author=self.staff.user)
            TopicFactory(forum=self.forum2, author=self.staff.user)
            TopicFactory(forum=self.forum3, author=self.staff.user)

        def test_get_last_topics(self):

            topics = Topic.objects.get_last_topics()
            self.assertEqual(2, len(topics))

        def test_get_unread_post(self):
            author = ProfileFactory()
            topic = TopicFactory(author=author.user, forum=self.forum1)
            post = PostFactory(topic=topic, position=1, author=author.user)
            topic.last_post = post
            topic.save()
            TopicRead(user=author.user, post=post, topic=topic).save()
            topic.last_post = PostFactory(author=self.staff.user, topic=topic, position=2)
            topic.save()
            TopicRead(post=topic.last_post, user=self.staff.user, topic=topic).save()
            self.assertEqual(1, len(TopicRead.objects.list_read_topic_pk(self.staff.user)))
            self.assertEqual(0, len(TopicRead.objects.list_read_topic_pk(author.user)))
