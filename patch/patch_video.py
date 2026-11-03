# 给 upstream 打视频任务 /content 回退补丁（A6API 等 OpenAI Videos 风格渠道）。
# 用法：python patch_video.py <upstream 仓库根目录>
# 写成独立文件，避免 PowerShell 下 python -c 的多层引号转义坑。
#
# 修复的问题：
# 1. 声明式协议轮询到 completed，但任务查询响应里没有视频 URL 时（如 A6API），
#    按 OpenAI Videos 规范回退到 GET /v1/videos/{task_id}/content 下载视频
#    （带渠道鉴权），而不是直接报"声明式协议已完成但没有返回结果"。
#    自动流程与"查询上游任务"都走 finishProtocolAdapterResult，一处修复两处生效。
# 2. parseAsyncMediaPoll 把 "object": "video" 这类类型标记误当成视频 URL，
#    产生伪引用；加 URL 合法性校验。
# 3. 人工转存（AdminRecoverVideoByURL）粘贴 /v1/videos/{id}/content 地址时，
#    用任务渠道的 BaseURL 重组地址并带渠道鉴权下载，而不是无鉴权裸 GET（会 401）。
#    鉴权信息只发往用户自己配置的渠道域名，不会泄漏到任意粘贴域名。
#
# Author: Passwd Word

import sys

root = sys.argv[1].rstrip("/\\")

T = "\t"
N = "\n"


def patch(path, subs):
    s = open(path, encoding="utf-8").read()
    for i, (old, new) in enumerate(subs):
        n = s.count(old)
        # 注意：断言文案必须纯 ASCII，Windows runner 默认 cp1252，中文会 UnicodeEncodeError
        assert n == 1, "%s anchor #%d hit %d times (expected 1)" % (path, i + 1, n)
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8").write(s)
    print("patched %s (%d subs)" % (path, len(subs)))


# ---------------- 1. backend/internal/protocol/builtin.go ----------------
p = root + "/backend/internal/protocol/builtin.go"
patch(p, [
    # 1a. "object": "video" 不是 URL：加合法性校验，伪引用不再产生
    (
        T + 'keys := []string{resultKind + "_url", resultKind + "Url", "result_url", "url"}' + N
        + T + 'if resultKind == "video" {' + N
        + T + T + 'keys = append(keys, "object")' + N
        + T + '}' + N
        + T + 'if value := firstString(payload, keys...); value != "" {' + N
        + T + T + 'references = append(references, MediaReference{URL: value, Kind: resultKind})' + N
        + T + '}',
        T + 'keys := []string{resultKind + "_url", resultKind + "Url", "result_url", "url"}' + N
        + T + 'if resultKind == "video" {' + N
        + T + T + 'keys = append(keys, "object")' + N
        + T + '}' + N
        + T + '// 上游任务查询经常带 "object": "video" 这类类型标记，它不是可下载的媒体地址；' + N
        + T + '// 必须校验确实是个 URL 才收录，否则会产生伪引用导致后续下载失败。' + N
        + T + 'if value := firstString(payload, keys...); isMediaURLValue(value) {' + N
        + T + T + 'references = append(references, MediaReference{URL: value, Kind: resultKind})' + N
        + T + '}',
    ),
    # 1b. 新增 isMediaURLValue 辅助函数
    (
        'func parseAsyncMediaPoll(c PollContext, payload map[string]any, capability Capability) (PollResult, error) {',
        '// isMediaURLValue 校验从上游响应提取的"媒体地址"确实是个可下载的 http(s) URL。' + N
        + 'func isMediaURLValue(value string) bool {' + N
        + T + 'value = strings.TrimSpace(value)' + N
        + T + 'if value == "" {' + N
        + T + T + 'return false' + N
        + T + '}' + N
        + T + 'parsed, err := url.Parse(value)' + N
        + T + 'if err != nil {' + N
        + T + T + 'return false' + N
        + T + '}' + N
        + T + 'switch strings.ToLower(parsed.Scheme) {' + N
        + T + 'case "http", "https":' + N
        + T + T + 'return parsed.Host != ""' + N
        + T + 'default:' + N
        + T + T + 'return false' + N
        + T + '}' + N
        + '}' + N
        + N
        + 'func parseAsyncMediaPoll(c PollContext, payload map[string]any, capability Capability) (PollResult, error) {',
    ),
])

# ---------------- 2. backend/internal/app/provider_protocol_result.go ----------------
p = root + "/backend/internal/app/provider_protocol_result.go"
patch(p, [
    # 2a. 无 ResultAdapter 声明时，按 OpenAI Videos 规范回退 /content
    (
        T + 'resultAdapter, ok := adapter.(protocol.ResultAdapter)' + N
        + T + 'capability, hasCapability := adapter.(protocol.ResultCapability)' + N
        + T + 'if !ok || !hasCapability || !capability.ResultAvailable() {' + N
        + T + T + 'return finishProtocolResult(ctx, input.Config, input.Mode, taskID, result, pollPolicy)' + N
        + T + '}',
        T + 'resultAdapter, ok := adapter.(protocol.ResultAdapter)' + N
        + T + 'capability, hasCapability := adapter.(protocol.ResultCapability)' + N
        + T + 'if !ok || !hasCapability || !capability.ResultAvailable() {' + N
        + T + T + '// OpenAI Videos 风格的上游（/v1/videos）在任务查询里只给状态不给 URL，' + N
        + T + T + '// 视频字节走独立的 /v1/videos/{task_id}/content 端点；放弃前最后试一次该规范端点。' + N
        + T + T + 'if output, handled, err := downloadOpenAIVideoContentResult(ctx, input, adapter, request, taskID, pollPolicy); handled {' + N
        + T + T + T + 'return output, err' + N
        + T + T + '}' + N
        + T + T + 'return finishProtocolResult(ctx, input.Config, input.Mode, taskID, result, pollPolicy)' + N
        + T + '}',
    ),
    # 2b. 新增回退辅助函数
    (
        'func protocolResultHasOutput(mode string, result *protocol.Result) bool {',
        '// isOpenAIVideosPollAdapter 判断协议插件是否走 OpenAI Videos 风格的任务接口。' + N
        + '// 按 OpenAI Videos API 规范，GET /v1/videos/{task_id} 只返回任务状态，' + N
        + '// 视频字节走独立的 GET /v1/videos/{task_id}/content 端点（需渠道鉴权）。' + N
        + 'func isOpenAIVideosPollAdapter(adapter protocol.Adapter) bool {' + N
        + T + 'if adapter == nil {' + N
        + T + T + 'return false' + N
        + T + '}' + N
        + T + 'return strings.Contains(adapter.Metadata().Poll, "/v1/videos/")' + N
        + '}' + N
        + N
        + '// downloadOpenAIVideoContentResult 在轮询已完成但未解析出媒体地址时，' + N
        + '// 按 OpenAI Videos 规范回退到 /v1/videos/{task_id}/content 下载视频（带渠道鉴权）。' + N
        + '// handled=false 表示不适用，调用方走原逻辑。' + N
        + 'func downloadOpenAIVideoContentResult(ctx context.Context, input canvasGenerationInput, adapter protocol.Adapter, request protocol.GenerationRequest, taskID string, pollPolicy videoPollPolicy) (map[string]interface{}, bool, error) {' + N
        + T + 'if input.Mode != "video" || !isOpenAIVideosPollAdapter(adapter) || strings.TrimSpace(taskID) == "" {' + N
        + T + T + 'return nil, false, nil' + N
        + T + '}' + N
        + T + 'spec := protocol.RequestSpec{Method: "GET", Path: "/v1/videos/" + taskID + "/content"}' + N
        + T + 'download := func(ctx context.Context) ([]byte, string, error) {' + N
        + T + T + 'return executeProtocolBinaryRequest(withProviderRequestKind(ctx, "download"), input.Config, spec)' + N
        + T + '}' + N
        + T + 'data, mimeType, err := runVideoDownload(ctx, taskID, pollPolicy, download)' + N
        + T + 'if err != nil {' + N
        + T + T + 'return nil, true, fmt.Errorf("声明式协议结果下载失败：%w", err)' + N
        + T + '}' + N
        + T + 'if len(data) == 0 {' + N
        + T + T + 'return nil, true, errors.New("声明式协议结果下载返回空内容")' + N
        + T + '}' + N
        + T + 'mimeType = strings.TrimSpace(strings.Split(mimeType, ";")[0])' + N
        + T + 'if mimeType == "" {' + N
        + T + T + 'mimeType = "application/octet-stream"' + N
        + T + '}' + N
        + T + 'reference := protocol.MediaReference{DataURL: dataURL(mimeType, data), MIMEType: mimeType}' + N
        + T + 'downloaded := &protocol.Result{Videos: []protocol.MediaReference{reference}}' + N
        + T + 'output, err := finishProtocolResult(ctx, input.Config, input.Mode, taskID, downloaded, pollPolicy)' + N
        + T + 'return output, true, err' + N
        + '}' + N
        + N
        + 'func protocolResultHasOutput(mode string, result *protocol.Result) bool {',
    ),
])

# ---------------- 3. backend/internal/app/provider_task_recovery.go ----------------
p = root + "/backend/internal/app/provider_task_recovery.go"
patch(p, [
    # 3a. 补 protocol 导入（转存鉴权下载用）
    (
        T + '"yingce/backend/internal/model"' + N
        + T + '"yingce/backend/internal/repository"',
        T + '"yingce/backend/internal/model"' + N
        + T + '"yingce/backend/internal/protocol"' + N
        + T + '"yingce/backend/internal/repository"',
    ),
    # 3b. 转存下载走鉴权感知的新函数
    (
        T + 'payload, err := downloadRemoteResource(parsed.String(), megabytes(policy.Resource.GeneratedFileMB)+1)' + N
        + T + 'if err != nil {' + N
        + T + T + 'return nil, err' + N
        + T + '}' + N
        + T + 'if !strings.HasPrefix(strings.ToLower(payload.mimeType), "video/") {' + N
        + T + T + 'return nil, BadAuthRequest("上游地址返回的不是视频文件")' + N
        + T + '}' + N
        + T + 'resultPayload := map[string]interface{}{"mode": "video", "video": map[string]interface{}{"dataUrl": dataURL(payload.mimeType, payload.data), "mimeType": payload.mimeType}}',
        T + 'transferData, transferMIME, err := s.downloadTransferVideo(ctx, task, parsed, megabytes(policy.Resource.GeneratedFileMB)+1)' + N
        + T + 'if err != nil {' + N
        + T + T + 'return nil, err' + N
        + T + '}' + N
        + T + 'if !strings.HasPrefix(strings.ToLower(transferMIME), "video/") {' + N
        + T + T + 'return nil, BadAuthRequest("上游地址返回的不是视频文件")' + N
        + T + '}' + N
        + T + 'resultPayload := map[string]interface{}{"mode": "video", "video": map[string]interface{}{"dataUrl": dataURL(transferMIME, transferData), "mimeType": transferMIME}}',
    ),
    # 3c. 新增转存鉴权下载辅助函数
    (
        'func (s *Service) AdminBatchQueryFailedVideoTasks(',
        '// errNoChannelConfig 表示任务没有可用的渠道配置，调用方回退到无鉴权下载。' + N
        + 'var errNoChannelConfig = errors.New("任务没有可用的渠道配置")' + N
        + N
        + '// isOpenAIVideoContentPath 判断是否为 OpenAI Videos 规范的内容端点路径' + N
        + '// （/v1/videos/{task_id}/content）。' + N
        + 'func isOpenAIVideoContentPath(path string) bool {' + N
        + T + 'parts := strings.Split(strings.Trim(strings.ToLower(path), "/"), "/")' + N
        + T + 'return len(parts) == 4 && parts[0] == "v1" && parts[1] == "videos" && parts[2] != "" && parts[3] == "content"' + N
        + '}' + N
        + N
        + '// downloadTransferVideo 下载人工转存的视频。粘贴的是 /v1/videos/{task_id}/content' + N
        + '// 这类上游内容地址时，用任务渠道的 BaseURL 重组地址并带渠道鉴权下载' + N
        + '// （裸 GET 会 401）；其他地址走原有无鉴权下载。' + N
        + '// 鉴权信息只发往用户自己配置的渠道域名，不会泄漏到任意粘贴域名。' + N
        + 'func (s *Service) downloadTransferVideo(ctx context.Context, task *model.Task, parsed *url.URL, maxBytes int64) ([]byte, string, error) {' + N
        + T + 'if isOpenAIVideoContentPath(parsed.Path) {' + N
        + T + T + 'data, mimeType, err := s.downloadChannelVideoContent(ctx, task, parsed)' + N
        + T + T + 'if err == nil {' + N
        + T + T + T + 'return data, mimeType, nil' + N
        + T + T + '}' + N
        + T + T + 'if !errors.Is(err, errNoChannelConfig) {' + N
        + T + T + T + '// 鉴权下载已尝试并失败，返回真实错误，不再回退裸下载。' + N
        + T + T + T + 'return nil, "", err' + N
        + T + T + '}' + N
        + T + '}' + N
        + T + 'payload, err := downloadRemoteResource(parsed.String(), maxBytes)' + N
        + T + 'if err != nil {' + N
        + T + T + 'return nil, "", err' + N
        + T + '}' + N
        + T + 'return payload.data, payload.mimeType, nil' + N
        + '}' + N
        + N
        + '// downloadChannelVideoContent 用任务渠道的鉴权下载 /v1/videos/{task_id}/content。' + N
        + 'func (s *Service) downloadChannelVideoContent(ctx context.Context, task *model.Task, parsed *url.URL) ([]byte, string, error) {' + N
        + T + 'decryptedInput, err := s.decryptTaskInputJSON(task.InputJSON)' + N
        + T + 'if err != nil {' + N
        + T + T + 'return nil, "", errNoChannelConfig' + N
        + T + '}' + N
        + T + 'var input canvasGenerationInput' + N
        + T + 'if err := json.Unmarshal([]byte(decryptedInput), &input); err != nil {' + N
        + T + T + 'return nil, "", errNoChannelConfig' + N
        + T + '}' + N
        + T + 'config, err := s.resolveProviderConfig(input.Config)' + N
        + T + 'if err != nil || strings.TrimSpace(config.BaseURL) == "" {' + N
        + T + T + 'return nil, "", errNoChannelConfig' + N
        + T + '}' + N
        + T + 'path := parsed.EscapedPath()' + N
        + T + 'if parsed.RawQuery != "" {' + N
        + T + T + 'path += "?" + parsed.RawQuery' + N
        + T + '}' + N
        + T + 'spec := protocol.RequestSpec{Method: "GET", Path: path}' + N
        + T + 'return executeProtocolBinaryRequest(withProviderRequestKind(ctx, "download"), config, spec)' + N
        + '}' + N
        + N
        + 'func (s *Service) AdminBatchQueryFailedVideoTasks(',
    ),
])

print("all video patches applied OK")
