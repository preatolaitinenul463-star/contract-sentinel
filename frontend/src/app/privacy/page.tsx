export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <h1 className="text-3xl font-bold">隐私政策</h1>
      <p className="text-sm text-muted-foreground">最后更新：2025年1月1日</p>

      <div className="prose prose-sm max-w-none space-y-6 text-muted-foreground">
        <section>
          <h2 className="text-lg font-semibold text-foreground">一、信息收集</h2>
          <p>我们收集以下类型的信息：</p>
          <p>1. <strong>账户信息</strong>：注册时提供的邮箱、姓名。</p>
          <p>2. <strong>合同文件</strong>：用户上传的合同文档内容。</p>
          <p>3. <strong>使用数据</strong>：使用本平台的操作日志、IP地址等。</p>
          <p>4. <strong>聊天记录</strong>：与法律助手的对话内容。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">二、信息使用</h2>
          <p>我们使用收集的信息用于：</p>
          <p>1. 提供合同审核、对比和咨询服务。</p>
          <p>2. 改进和优化平台功能。</p>
          <p>3. 保障平台安全和防止滥用。</p>
          <p>4. 我们<strong>不会</strong>将您的合同内容用于AI模型训练。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">三、数据安全</h2>
          <p>1. 所有合同文件均经过加密存储（AES-256）。</p>
          <p>2. 发送至AI模型的文本经过脱敏处理，去除敏感个人信息。</p>
          <p>3. 所有API通信使用HTTPS加密传输。</p>
          <p>4. 访问日志保留用于安全审计。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">四、第三方服务</h2>
          <p>本平台使用以下第三方AI服务处理合同内容：</p>
          <p>1. DeepSeek API：用于合同审核和智能问答。</p>
          <p>2. MiniMax API：用于文本向量化（语义检索）。</p>
          <p>发送至第三方的数据已经过脱敏处理，不包含可识别个人的敏感信息。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">五、数据保留</h2>
          <p>1. 默认长期保存用户数据，以便用户持续查询历史记录和导出。</p>
          <p>2. 用户可随时在设置中发起数据导出与账号注销。</p>
          <p>3. 平台保留为安全审计目的留存必要日志的权利。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">六、用户权利</h2>
          <p>根据《个人信息保护法》，您享有以下权利：</p>
          <p>1. <strong>访问权</strong>：查看我们收集的您的个人信息。</p>
          <p>2. <strong>更正权</strong>：更正不准确的个人信息。</p>
          <p>3. <strong>删除权</strong>：要求删除您的个人信息和数据。</p>
          <p>4. <strong>导出权</strong>：导出您的数据副本。</p>
          <p>5. <strong>注销权</strong>：注销您的账户。</p>
          <p>6. <strong>隔离权</strong>：不同账户数据之间不互通，您可就异常访问申请核查。</p>
          <p>您可以在"设置"页面行使上述权利，或联系我们。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">七、联系我们</h2>
          <p>如对本隐私政策有任何疑问，请联系：</p>
          <p>邮箱：2606536766@qq.com</p>
        </section>
      </div>
    </div>
  );
}
