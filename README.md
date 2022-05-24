## Running Locally

Install docker. Build image:

```
docker build --tag auv-wiki .
```

Run container.

```
docker run -p 3000:3000 -dit --name auv-wiki -v content:/opt/raneto/example/content auv-wiki
```

Editing files inside content should reflect changes in the application (and vice-versa).
