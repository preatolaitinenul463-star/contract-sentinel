export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <h1 className="text-3xl font-bold">用户服务协议</h1>
      <p className="text-sm text-muted-foreground">最后更新：2025年1月1日</p>

      <div className="prose prose-sm max-w-none space-y-6 text-muted-foreground">
        <section>
          <h2 className="text-lg font-semibold text-foreground">一、服务说明</h2>
          <p>合同哨兵（以下简称"本平台"）是一个基于人工智能技术的合同审核、对比和法务咨询平台。本平台提供的分析结果和建议仅供参考，不构成正式法律意见。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">二、用户注册</h2>
          <p>1. 用户在注册时应提供真实、准确的个人信息。</p>
          <p>2. 用户应妥善保管账号和密码，对其账号下的所有行为承担责任。</p>
          <p>3. 如发现账号被盗用，请立即通知我们。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">三、服务内容</h2>
          <p>1. 合同智能审核：通过AI分析合同风险条款。</p>
          <p>2. 合同对比：分析两份合同之间的差异。</p>
          <p>3. 法律助手：基于法规库的智能问答服务。</p>
          <p>4. 以上服务均依赖AI模型生成，可能存在误判，用户应自行判断和验证。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">四、免责声明</h2>
          <p>1. 本平台提供的审核结果和法律建议仅供参考，不替代专业律师的法律意见。</p>
          <p>2. 用户因依赖本平台提供的信息而做出的决策，本平台不承担法律责任。</p>
          <p>3. 涉及重大法律决策时，请务必咨询持证律师。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">五、知识产权</h2>
          <p>1. 用户上传的合同文件，知识产权归用户所有。</p>
          <p>2. 本平台生成的审核报告，用户享有使用权。</p>
          <p>3. 本平台的软件、算法、界面设计等知识产权归本平台所有。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">六、数据安全</h2>
          <p>1. 我们采用加密技术保护用户数据安全。</p>
          <p>2. 未经用户授权，我们不会向第三方提供用户数据。</p>
          <p>3. 详见《隐私政策》。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">七、协议修改</h2>
          <p>本平台有权修改本协议，修改后的协议将在平台公布。用户继续使用本平台即表示接受修改后的协议。</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-foreground">八、联系方式</h2>
          <p>如有任何问题，请联系：support@contract-sentinel.ai</p>
        </section>
      </div>
    </div>
  );
}
