# Como publicar no PyPI

O workflow de release já está pronto. Falta uma configuração que só você pode fazer,
porque envolve criar conta. Leva uns cinco minutos e não custa nada.

Depois disso, publicar uma versão nova é criar uma tag. Nenhum token fica guardado
em lugar nenhum: o GitHub prova a identidade do workflow por OIDC e o PyPI emite uma
credencial temporária na hora. É o método que o próprio PyPI recomenda hoje.

## Uma vez só

**1. Crie a conta** em [pypi.org/account/register](https://pypi.org/account/register/)
e ative a autenticação em dois fatores. O PyPI exige 2FA para publicar.

**2. Registre o publicador confiável.** Como o pacote `rtc-check` ainda não existe lá,
use o formulário de projeto pendente:
[pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)

Preencha exatamente assim:

| Campo | Valor |
|---|---|
| PyPI Project Name | `rtc-check` |
| Owner | `TaynanGT` |
| Repository name | `rtc-check` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

**3. Crie o environment no GitHub.** Em Settings → Environments → New environment,
com o nome `pypi`. Se quiser um freio de mão, marque "Required reviewers" e coloque
você mesmo: aí toda publicação espera sua aprovação num clique.

**4. Ligue o interruptor:**

```bash
gh variable set PYPI_HABILITADO --body true
```

Enquanto essa variável não existir, o job do PyPI é pulado. Isso é de propósito:
sem ela, a primeira tag falharia com `invalid-publisher` e deixaria o release
vermelho por causa de uma etapa que ainda não foi configurada. Foi exatamente o
que aconteceu na v0.1.0.

## Toda vez que for publicar

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

O workflow então roda lint, tipos e testes, monta o wheel, confere que a versão da tag
bate com a do pacote, anexa os arquivos ao release do GitHub e publica no PyPI.

Se a versão da tag não bater com `__version__`, ele para antes de publicar. Isso evita
o clássico de subir `v0.2.0` com o código ainda dizendo `0.1.0`.

## Antes de subir uma versão nova

1. Atualize `version` no `pyproject.toml` e `__version__` em `src/rtc_check/__init__.py`
2. Escreva o que mudou no `CHANGELOG.md`
3. Commite, aí sim crie a tag

## Depois que estiver no PyPI

Volte no README e na landing e troque a instrução de instalação de
`pip install git+https://...` para `pip install rtc-check`. Hoje as duas dizem
explicitamente que ainda não está no PyPI, e isso precisa deixar de ser verdade
antes do texto mudar.
