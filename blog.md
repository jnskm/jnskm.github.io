---
layout: default
title: "Blog"
permalink: blog/
---

<div class="main-content">
  <ul class="post-list">
    {% assign blog_posts = site.posts | where: "category", "blog" %}
    {% for post in blog_posts %}
      <li>
        <div class="post-item">
          <span class="post-date">{{ post.date | date: "%Y.%m.%d" }}</span>
          <a class="post-title" href="{{ post.url | relative_url }}">{{ post.title }}</a>
        </div>
      </li>
    {% endfor %}
  </ul>
</div>