---
layout: default
title: "Devotionals"
permalink: /devotionals/
---

<div class="main-content">
  <ul class="post-list">
    {% assign devotionals = site.posts | where: "categories", "devotional" | sort: "date" | reverse %}
    {% for post in devotionals %}
      <li>
        <div class="post-item">
          <span class="post-date">{{ post.date | date: "%Y.%m.%d" }}</span>
          <a class="post-title" href="{{ post.url | relative_url }}">{{ post.title }}</a>
        </div>
      </li>
    {% endfor %}
  </ul>
</div>