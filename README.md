# Portfolio — Thang Nguyen

## Cấu trúc
```
index.html      giao diện + hiệu ứng (client không sửa)
content.json    toàn bộ chữ, link, đường dẫn ảnh, SEO (client sửa qua Pages CMS)
tuning.json     thông số hiệu ứng (designer sửa)
.pages.yml      cấu hình form của Pages CMS
images/         ảnh: avatar, icons/, projects/, og-image.jpg
scripts/build.py            tạo bản deploy trong _site/ (ghi Title/Meta/OG vào HTML)
.github/workflows/deploy.yml  GitHub Actions: tự build + deploy mỗi lần có thay đổi trên main
```

## SEO (Title, Meta description, OG image)
Mục `seo` trong `content.json`. Facebook, Zalo và LinkedIn không chạy JavaScript, nên các thẻ này **được ghi thẳng vào HTML lúc deploy** (`scripts/build.py`), không phải lúc trang tải. Build tạo ra:
- `index.html`, `about/index.html`, `work/<slug>/index.html` (mỗi trang có title riêng), `404.html`
- `sitemap.xml`, `robots.txt`
- Nếu `seo.siteUrl` để trống, build tự lấy tên miền đang cấu hình trên GitHub Pages.
- OG image nên là JPG/PNG 1200×630.

Chạy thử build trên máy: `python scripts/build.py`, rồi mở thư mục `_site` bằng một web server.

## Xem thử trên máy
Trang đọc `content.json` bằng `fetch`, nên **không mở trực tiếp file bằng double-click** được. Hãy chạy một web server nhỏ trong thư mục này:

- VS Code: cài extension **Live Server**, chuột phải vào `index.html` rồi chọn *Open with Live Server*
- hoặc: `npx serve .` / `python -m http.server`

Lúc xem trên máy, hãy mở `http://localhost:xxxx/index.html`. Khi URL kết thúc bằng `.html`, trang tự chuyển sang kiểu đường dẫn `#/about`, nên chuyển trang qua lại vẫn chạy mà không cần server hỗ trợ rewrite.

## Thẻ `<base>` (trong `<head>`)
Một đoạn script nhỏ trong `<head>` tự nhận thư mục gốc: trên tên miền riêng là `/`, trên `ten.github.io/ten-repo/` là `/ten-repo/`. Bạn không cần sửa tay, và cũng không cần build lại khi đổi tên miền.

## Bảng chỉnh hiệu ứng (phím G)
- Bật/tắt: `settings.tuningPanel` trong `content.json` (`true` / `false`), hoặc trong Pages CMS vào mục **Cài đặt nâng cao**.
- Thông số dùng cho mọi người xem nằm trong **`tuning.json`** (tách khỏi `content.json` để client không đụng tới). Chỉnh xong, bấm **Copy settings (JSON)** trong bảng rồi dán vào mục `effects` của `tuning.json` trên GitHub.
- Nếu chưa dán vào `tuning.json`, thông số bạn chỉnh chỉ được lưu trong trình duyệt của bạn.
- Khi `tuningPanel` = `false`, phím G không còn tác dụng và các thông số lưu trong trình duyệt bị bỏ qua.

## Pages CMS
`.pages.yml` khai báo form cho **toàn bộ** các trường trong `content.json`. Khi thêm trường mới vào `content.json`, nhớ khai báo luôn trong `.pages.yml`.
Ảnh client upload được lưu vào `images/` và tự đổi tên an toàn (bỏ dấu, bỏ khoảng trắng).

## Ghi chú về dữ liệu
- `settings.startProject`: project đứng giữa khi mở trang (đếm từ 1)
- `projects[].pages`: danh sách ảnh trang chi tiết theo thứ tự. Nếu để trống, trang sẽ hiện `placeholderPages` ô xám.
- `projects[].slug`: có thể để trống, khi đó slug được tạo tự động từ tên project. Đã đăng rồi thì không nên đổi, vì link `/work/<slug>` sẽ hỏng.
- Ảnh thiếu hoặc sai đường dẫn sẽ hiện ô xám có tên project, trang không bị vỡ.
- `about.stats`: bố cục chỉ có 3 vị trí.
- Tối đa **6 dự án** hiển thị (`MAX_PROJECTS` trong `index.html`, `[:6]` trong `build.py`, `list.max: 6` trong `.pages.yml`). Trên mobile, danh sách Work và cột ảnh tự đẩy lên theo số dự án (`--wx`).
- Mobile: card đang active opacity 100%, card khác 70% (`alpha` trong `layoutCards()`, cả WebGL lẫn DOM). Nút mũi tên cố định ở góc card.
- `projects[].hidden: true`: ẩn dự án khỏi website (không có trang `/work/...`, không có trong sitemap), nội dung vẫn được giữ lại.
- Tên dự án dài ở mục "Next project" tự thu nhỏ chữ (`fitNextName()`), tối đa 2 dòng, không đẩy ảnh ra ngoài.
