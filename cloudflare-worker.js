// Cloudflare Worker：反向代理 Hugging Face Space
// 作用：把你的 Worker 域名 (xxx.workers.dev) 的所有请求转发到 HF Space，
// 让大陆用户通过 Cloudflare 节点访问，绕过 hf.space 直连不稳的问题。
//
// 用法：登录 Cloudflare → Workers & Pages → Create Worker → 把本文件内容
// 整段粘贴进编辑器 → Deploy。然后访问分配给你的 https://xxx.workers.dev 即可。
//
// 如果以后 HF 用户名/空间名变了，只改下面这一行。

const TARGET_HOST = "linanuyx-eco.hf.space";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    // 把访问者请求的 host 换成 HF Space 的 host，路径/查询参数原样保留
    url.hostname = TARGET_HOST;
    url.protocol = "https:";
    url.port = "";

    // 复制请求头，改写 Host，避免把访问者的 host 传给后端导致路由错乱
    const headers = new Headers(request.headers);
    headers.set("Host", TARGET_HOST);

    const proxyReq = new Request(url.toString(), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "follow",
    });

    const resp = await fetch(proxyReq);

    // 透传响应；加一个 CORS 头以防万一（同源访问其实不需要，但无害）
    const respHeaders = new Headers(resp.headers);
    respHeaders.set("Access-Control-Allow-Origin", "*");

    return new Response(resp.body, {
      status: resp.status,
      statusText: resp.statusText,
      headers: respHeaders,
    });
  },
};
